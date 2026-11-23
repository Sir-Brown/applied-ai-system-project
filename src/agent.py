"""
The music agent: plan, act, check, revise.

    request -> guardrails -> retrieve -> plan (profile) -> recommend -> critique
                                                              ^            |
                                                              +-- revise <-+   (max 2 times)

Retrieval is not decoration: the retrieved chunks ARE the taste profile, so a
request like "late-night coding, nothing too loud" only works because the
glossary documents were found. The critic is not decoration either: when it
finds a problem (e.g. the requested genre is not in the catalog) the agent
changes its plan and re-ranks before answering.

ask() never raises for bad input. It returns an AgentResult whose status says what happened.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.confidence import REVIEW_THRESHOLD, Assessment, assess, fit_of
from src.guardrails import GuardrailError, validate_catalog, validate_profile, validate_request
from src.recommender import DEFAULT_MODE, MODES, recommend_songs
from src.retriever import KIND_PRIORITY, Hit, Retriever, build_retriever

log = logging.getLogger("musicagent.agent")

MAX_REVISIONS = 2
TOP_K = 5

Recommendations = List[Tuple[Dict, float, str]]


@dataclass
class Plan:
    """The agent's interpretation of the request."""
    profile: Dict
    mode: str = DEFAULT_MODE
    diversity: bool = False
    grounded: Set[str] = field(default_factory=set)   # core fields that came from the user's words
    dropped: Set[str] = field(default_factory=set)    # requested fields the agent had to give up on
    sources: List[str] = field(default_factory=list)  # which retrieved documents were used
    assumptions: List[str] = field(default_factory=list)


@dataclass
class AgentResult:
    status: str                        # ok | needs_review | no_match | rejected | error
    message: str
    request: str = ""
    plan: Optional[Plan] = None
    recommendations: Recommendations = field(default_factory=list)
    assessment: Optional[Assessment] = None
    revisions: int = 0
    trace: List[str] = field(default_factory=list)


def _default_profile() -> Dict:
    return {
        "favorite_genre": None,
        "favorite_mood": None,
        "target_energy": 0.5,
        "likes_acoustic": False,
    }


class Planner:
    """Turns retrieved chunks into a taste profile. No guessing beyond what the documents say."""

    FIELD_MAP = {  # chunk field -> (profile key, is it one of the core fields?)
        "genre": ("favorite_genre", "genre"),
        "mood": ("favorite_mood", "mood"),
        "energy": ("target_energy", "energy"),
        "acoustic": ("likes_acoustic", None),
        "detailed_mood": ("preferred_detailed_mood", None),
        "instrumental": ("prefers_instrumental", None),
        "decade": ("preferred_decade", None),
    }

    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def plan(self, text: str) -> Tuple[Plan, List[Hit]]:
        hits = self.retriever.search(text)
        plan = Plan(profile=_default_profile())

        usable: List[Hit] = []
        for hit in hits:
            if hit.negated and not hit.chunk.negatable:
                plan.assumptions.append(f"ignored '{hit.matched[0]}' because it was negated (e.g. 'no {hit.matched[0]}')")
            else:
                usable.append(hit)

        # Activities first, then moods, then genres, then modifiers. Within a kind the
        # strongest match is applied last, so it wins any conflict.
        usable.sort(key=lambda h: (KIND_PRIORITY[h.chunk.kind], h.score))
        for hit in usable:
            self._apply(plan, hit)

        for core, label in (("genre", "genre"), ("mood", "mood"), ("energy", "energy level")):
            if core not in plan.grounded:
                plan.assumptions.append(f"no {label} mentioned, so it was left {'open' if core != 'energy' else 'at the default 0.5'}")
        return plan, usable

    def _apply(self, plan: Plan, hit: Hit) -> None:
        chunk, negated = hit.chunk, hit.negated
        label = f"{chunk.title} [{chunk.source}] via {', '.join(repr(m) for m in hit.matched)}"
        if negated:
            label += " (negated, so its effect is flipped)"
        used = False

        for key, value in chunk.fields.items():
            if key == "energy_delta":
                delta = -value if negated else value
                plan.profile["target_energy"] = plan.profile["target_energy"] + delta
                plan.grounded.add("energy")
                used = True
            elif key == "diverse":
                plan.diversity = True
                used = True
            elif key in self.FIELD_MAP:
                profile_key, core = self.FIELD_MAP[key]
                if isinstance(value, bool) and negated:
                    value = not value
                plan.profile[profile_key] = value
                if core:
                    plan.grounded.add(core)
                used = True
        if used and label not in plan.sources:
            plan.sources.append(label)


class MusicAgent:
    """Plan -> act -> critique -> revise, with guardrails and logging at every step."""

    def __init__(self, songs: List[Dict], retriever: Optional[Retriever] = None,
                 use_retrieval: bool = True, knowledge_dir: Optional[Path] = None,
                 max_revisions: int = MAX_REVISIONS):
        validate_catalog(songs)
        self.songs = songs
        self.max_revisions = max_revisions
        self.retriever = retriever or build_retriever(songs, knowledge_dir, use_glossary=use_retrieval)
        self.planner = Planner(self.retriever)
        self.catalog_genres = {s["genre"].strip().lower() for s in songs}
        self.catalog_moods = {s["mood"].strip().lower() for s in songs}

    # ------------------------------------------------------------------ public API
    def ask(self, text: object, k: int = TOP_K) -> AgentResult:
        trace: List[str] = []
        try:
            return self._ask(text, k, trace)
        except GuardrailError as exc:  # expected refusals
            log.warning("request refused (%s): %r", exc.code, str(text)[:80])
            trace.append(f"guardrail: refused [{exc.code}]")
            return AgentResult("rejected", exc.user_message, str(text)[:80], trace=trace)
        except Exception:  # noqa: BLE001 - last-resort net: log everything, show the user nothing scary
            log.exception("unexpected failure while handling %r", str(text)[:80])
            trace.append("error: unexpected failure (see logs/agent.log)")
            return AgentResult("error", "Something went wrong on my side. The details were logged.",
                               str(text)[:80], trace=trace)

    # ------------------------------------------------------------------ pipeline
    def _ask(self, text: object, k: int, trace: List[str]) -> AgentResult:
        request = validate_request(text)
        trace.append(f"guardrail: request accepted ({len(request)} chars)")
        log.info("request: %r", request)

        plan, hits = self.planner.plan(request)
        trace.append(f"retrieve: {len(hits)} usable chunk(s): " + (", ".join(plan.sources) or "none"))
        if not plan.sources:
            log.info("no relevant documents for %r", request)
            trace.append("decide: nothing retrieved, so no guess is made")
            return AgentResult(
                "no_match",
                "I could not find a music preference in that request. Try mentioning an activity, "
                "genre, mood or energy level, e.g. 'upbeat music for a road trip'.",
                request, plan, trace=trace,
            )

        plan.profile, fixes = validate_profile(plan.profile)
        plan.assumptions.extend(fixes)
        trace.append(f"plan: genre={plan.profile['favorite_genre']}, mood={plan.profile['favorite_mood']}, "
                     f"energy={plan.profile['target_energy']}, acoustic={plan.profile['likes_acoustic']}, "
                     f"mode={plan.mode}, diversity={plan.diversity}")

        recs, assessment, revisions = self._act_and_revise(plan, k, trace)

        status = "ok" if assessment.confidence >= REVIEW_THRESHOLD else "needs_review"
        if status == "ok":
            message = f"Here are your top {len(recs)} songs."
        else:
            message = (f"Here are my best guesses, but confidence is low ({assessment.confidence:.2f}), "
                       "so please treat them as suggestions and check them yourself.")
        trace.append(f"decide: status={status}, confidence={assessment.confidence:.2f}, revisions={revisions}")
        log.info("result status=%s confidence=%.2f revisions=%d top=%s", status, assessment.confidence,
                 revisions, recs[0][0]["title"] if recs else None)
        return AgentResult(status, message, request, plan, recs, assessment, revisions, trace)

    def _act_and_revise(self, plan: Plan, k: int, trace: List[str]):
        revisions = 0
        while True:
            recs = recommend_songs(plan.profile, self.songs, k, mode=plan.mode, diversity=plan.diversity)
            assessment = assess(plan.profile, plan.mode, recs, plan.grounded,
                                self.catalog_genres, self.catalog_moods, plan.dropped, plan.diversity)
            trace.append(f"recommend: mode={plan.mode}, top={recs[0][0]['title'] if recs else None}")
            trace.append(f"critique: {assessment.summary()}")

            if not assessment.issues or revisions >= self.max_revisions:
                if assessment.issues and revisions >= self.max_revisions:
                    trace.append("revise: revision limit reached, stopping")
                return recs, assessment, revisions

            changes = self._revise(plan, assessment, k)
            if not changes:
                trace.append("revise: no further fix available, stopping")
                return recs, assessment, revisions
            revisions += 1
            for change in changes:
                trace.append(f"revise #{revisions}: {change}")
                plan.assumptions.append(change)
                log.info("revision %d: %s", revisions, change)

    def _revise(self, plan: Plan, assessment: Assessment, k: int) -> List[str]:
        """Change the plan to address the critic's issues. Returns what changed (empty = nothing to try)."""
        changes: List[str] = []
        issues = set(assessment.issues)

        if "genre_not_in_catalog" in issues:
            changes.append(f"genre '{plan.profile['favorite_genre']}' is not in the catalog; "
                           "dropped it and rely on mood and energy instead")
            plan.profile["favorite_genre"] = None
            plan.grounded.discard("genre")
            plan.dropped.add("genre")
        if "mood_not_in_catalog" in issues:
            changes.append(f"mood '{plan.profile['favorite_mood']}' is not in the catalog; dropped it")
            plan.profile["favorite_mood"] = None
            plan.grounded.discard("mood")
            plan.dropped.add("mood")
        if "repetitive" in issues and not plan.diversity:
            plan.diversity = True
            changes.append("top results repeat an artist or genre; turned the diversity penalty on")
        if "low_fit" in issues and not changes:
            best_mode, best_fit = plan.mode, assessment.fit
            for name in MODES:
                trial = recommend_songs(plan.profile, self.songs, k, mode=name, diversity=plan.diversity)
                trial_fit = fit_of(plan.profile, name, trial)
                if trial_fit > best_fit + 0.02:
                    best_mode, best_fit = name, trial_fit
            if best_mode != plan.mode:
                changes.append(f"fit {assessment.fit:.2f} was low; switched scoring mode "
                               f"{plan.mode} -> {best_mode} (fit {best_fit:.2f})")
                plan.mode = best_mode
        return changes
