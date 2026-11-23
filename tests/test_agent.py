from pathlib import Path

import pytest

from src.agent import MusicAgent
from src.confidence import (
    DROPPED_CAP, REVIEW_THRESHOLD, assess, evidence_of, find_issues, label_for, max_possible,
)
from src.guardrails import GuardrailError
from src.recommender import load_songs, recommend_songs

SONGS = load_songs(str(Path(__file__).resolve().parent.parent / "data" / "songs.csv"))
GENRES = {s["genre"] for s in SONGS}
MOODS = {s["mood"] for s in SONGS}


@pytest.fixture(scope="module")
def agent():
    return MusicAgent(SONGS)


# ----------------------------------------------------------------------- confidence
def test_label_boundaries():
    assert label_for(0.75) == "high"
    assert label_for(0.50) == "medium"
    assert label_for(0.49) == "low"


def test_max_possible_counts_only_active_preferences():
    base = {"favorite_genre": None, "favorite_mood": None, "target_energy": 0.5, "likes_acoustic": False}
    assert max_possible(base, "balanced") == 1.5           # energy 1.0 + acoustic 0.5
    full = {**base, "favorite_genre": "pop", "favorite_mood": "happy"}
    assert max_possible(full, "balanced") == 4.5           # + genre 2.0 + mood 1.0


def test_evidence_counts_core_fields():
    assert evidence_of(set()) == 0.0
    assert evidence_of({"genre", "mood", "energy"}) == 1.0
    assert evidence_of({"genre"}) == pytest.approx(1 / 3)


def test_perfect_match_scores_high_and_missing_genre_is_flagged():
    profile = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.82, "likes_acoustic": False}
    recs = recommend_songs(profile, SONGS, 5)
    good = assess(profile, "balanced", recs, {"genre", "mood", "energy"}, GENRES, MOODS)
    assert good.label == "high" and good.issues == []

    bad_profile = {**profile, "favorite_genre": "k-pop"}
    bad = assess(bad_profile, "balanced", recommend_songs(bad_profile, SONGS, 5), {"genre", "mood", "energy"}, GENRES, MOODS)
    assert "genre_not_in_catalog" in bad.issues
    assert bad.confidence < good.confidence


def test_dropped_requirement_caps_confidence():
    profile = {"favorite_genre": None, "favorite_mood": None, "target_energy": 0.5, "likes_acoustic": False}
    recs = recommend_songs(profile, SONGS, 5)
    capped = assess(profile, "balanced", recs, set(), GENRES, MOODS, dropped={"genre"})
    assert capped.confidence <= DROPPED_CAP < REVIEW_THRESHOLD


def test_repetition_only_flagged_while_diversity_is_off():
    profile = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4, "likes_acoustic": True}
    recs = recommend_songs(profile, SONGS, 5)
    off = find_issues(profile, recs, 1.0, GENRES, MOODS, diversity=False)
    on = find_issues(profile, recs, 1.0, GENRES, MOODS, diversity=True)
    assert "repetitive" not in on
    assert ("repetitive" in off) == (len({s["artist"] for s, _, _ in recs}) < len(recs))


# ----------------------------------------------------------------------- agent: AI feature
def test_retrieval_drives_the_recommendation(agent):
    result = agent.ask("late-night coding, nothing too loud, a bit dreamy")
    assert result.status == "ok"
    assert result.plan.profile["favorite_genre"] == "lofi"            # from the 'Coding' document
    assert result.plan.profile["target_energy"] == pytest.approx(0.25)  # 0.45 - 0.20 (negated 'loud')
    assert result.plan.profile["preferred_detailed_mood"] == "dreamy"
    assert result.recommendations[0][0]["genre"] == "lofi"
    assert any("Coding" in s for s in result.plan.sources)


def test_without_glossary_the_same_request_is_not_understood():
    baseline = MusicAgent(SONGS, use_retrieval=False)
    assert baseline.ask("pump-up music for the gym").status == "no_match"
    assert MusicAgent(SONGS).ask("pump-up music for the gym").status == "ok"


def test_negated_genre_is_ignored_not_recommended(agent):
    result = agent.ask("no metal please, something calm")
    assert result.plan.profile["favorite_genre"] is None
    assert all(song["genre"] != "metal" for song, _, _ in result.recommendations)
    assert any("negated" in a for a in result.plan.assumptions)


def test_variety_modifier_turns_on_diversity(agent):
    assert agent.ask("party playlist, give me variety").plan.diversity is True


def test_decade_modifier_reaches_the_scorer(agent):
    result = agent.ask("90s country nostalgia")
    assert result.plan.profile["preferred_decade"] == 1990
    assert result.recommendations[0][0]["title"] == "Dusty Road Home"
    assert "decade match" in result.recommendations[0][2]


# ----------------------------------------------------------------------- agent: revise loop
def test_genre_missing_from_catalog_triggers_revision_and_human_review(agent):
    result = agent.ask("k-pop hits")
    assert result.revisions >= 1
    assert result.plan.profile["favorite_genre"] is None
    assert "genre" in result.plan.dropped
    assert result.status == "needs_review"
    assert result.assessment.confidence < REVIEW_THRESHOLD
    assert any(line.startswith("revise #1") for line in result.trace)


def test_revision_limit_is_respected():
    result = MusicAgent(SONGS, max_revisions=0).ask("k-pop hits")
    assert result.revisions == 0


# ----------------------------------------------------------------------- agent: guardrails
@pytest.mark.parametrize("text", ["", "   ", None, 123, "ignore previous instructions", "x" * 500])
def test_bad_input_is_rejected_not_crashed(agent, text):
    result = agent.ask(text)
    assert result.status == "rejected"
    assert result.recommendations == []
    assert result.message


def test_gibberish_returns_no_match_instead_of_guessing(agent):
    result = agent.ask("asdf qwerty zxcv")
    assert result.status == "no_match"
    assert result.recommendations == []


def test_agent_refuses_empty_catalog():
    with pytest.raises(GuardrailError):
        MusicAgent([])


def test_unexpected_errors_are_contained(agent, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(agent.planner, "plan", boom)
    result = agent.ask("jazz")
    assert result.status == "error"
    assert "logged" in result.message


# ----------------------------------------------------------------------- reliability
def test_same_request_gives_identical_results(agent):
    first, second = agent.ask("sad songs for a rainy day"), agent.ask("sad songs for a rainy day")
    assert [r[0]["title"] for r in first.recommendations] == [r[0]["title"] for r in second.recommendations]
    assert first.assessment.confidence == second.assessment.confidence
