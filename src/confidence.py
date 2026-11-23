"""
The critic: scores how much to trust a set of recommendations and names what is wrong.

Confidence (0-1) blends three signals:
  fit         how close the best song's score is to the best score this profile could earn
  evidence    how many of genre / mood / energy came from the user's words instead of defaults
  separation  how far the top pick stands above the 5th pick (a flat list means a weak signal)

It also reports "issues" that the agent can act on during its revise step.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Set, Tuple, Union

from src.recommender import (
    DECADE_WEIGHT, DETAILED_MOOD_WEIGHT, INSTRUMENTAL_WEIGHT, LANGUAGE_WEIGHT, MODES,
    POPULARITY_WEIGHT, ScoringMode,
)

FIT_WEIGHT, EVIDENCE_WEIGHT, SEPARATION_WEIGHT = 0.55, 0.25, 0.20
CATALOG_GAP_PENALTY = 0.20
DROPPED_CAP = 0.45           # max confidence when a requested genre/mood had to be dropped
LOW_FIT = 0.60               # below this the critic asks for a revision
HIGH_CONFIDENCE = 0.75
REVIEW_THRESHOLD = 0.50      # below this the result is flagged for a human
CORE_FIELDS = ("genre", "mood", "energy")

Recommendations = Sequence[Tuple[Dict, float, str]]


@dataclass
class Assessment:
    confidence: float
    label: str                       # high | medium | low
    fit: float
    evidence: float
    separation: float
    issues: List[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = f"fit {self.fit:.2f}, evidence {self.evidence:.2f}, separation {self.separation:.2f}"
        issues = f"; issues: {', '.join(self.issues)}" if self.issues else ""
        return f"confidence {self.confidence:.2f} ({self.label}) [{parts}]{issues}"


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def label_for(confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE:
        return "high"
    return "medium" if confidence >= REVIEW_THRESHOLD else "low"


def max_possible(profile: Dict, mode: Union[str, ScoringMode]) -> float:
    """Highest score any song could earn for this profile under this scoring mode."""
    weights = MODES[mode] if isinstance(mode, str) else mode
    total = weights.energy + weights.acoustic  # always scored
    if profile.get("favorite_genre"):
        total += weights.genre
    if profile.get("favorite_mood"):
        total += weights.mood
    if profile.get("preferred_decade") is not None:
        total += DECADE_WEIGHT
    if profile.get("preferred_detailed_mood"):
        total += DETAILED_MOOD_WEIGHT
    if profile.get("target_popularity") is not None:
        total += POPULARITY_WEIGHT
    if profile.get("prefers_instrumental") is not None:
        total += INSTRUMENTAL_WEIGHT
    if profile.get("preferred_language"):
        total += LANGUAGE_WEIGHT
    return total


def fit_of(profile: Dict, mode: Union[str, ScoringMode], recs: Recommendations) -> float:
    """Top score divided by the best possible score (0 when there are no results)."""
    if not recs:
        return 0.0
    return _clamp(recs[0][1] / max_possible(profile, mode))


def evidence_of(grounded: Set[str]) -> float:
    """Fraction of the core fields (genre, mood, energy) that came from the user's words."""
    return sum(1 for f in CORE_FIELDS if f in grounded) / len(CORE_FIELDS)


def separation_of(profile: Dict, mode: Union[str, ScoringMode], recs: Recommendations) -> float:
    """Gap between the 1st and last pick, as a share of 30% of the possible score."""
    if len(recs) < 2:
        return 0.0
    gap = recs[0][1] - recs[-1][1]
    return _clamp(gap / (0.30 * max_possible(profile, mode)))


def find_issues(
    profile: Dict, recs: Recommendations, fit: float,
    catalog_genres: Set[str], catalog_moods: Set[str], diversity: bool = False,
) -> List[str]:
    issues: List[str] = []
    if not recs:
        return ["no_results"]
    genre, mood = profile.get("favorite_genre"), profile.get("favorite_mood")
    if genre and genre.lower() not in catalog_genres:
        issues.append("genre_not_in_catalog")
    if mood and mood.lower() not in catalog_moods:
        issues.append("mood_not_in_catalog")
    if fit < LOW_FIT:
        issues.append("low_fit")
    # Repetition is only an issue while the diversity penalty is still off (it is the one
    # thing the agent can change), and only for a repeated artist or 3+ songs from a genre
    # the user did not ask for.
    artists = [s["artist"].strip().lower() for s, _, _ in recs]
    genres = [s["genre"].strip().lower() for s, _, _ in recs if s["genre"].strip().lower() != (genre or "").lower()]
    repeats = len(set(artists)) < len(artists) or (genres and max(genres.count(g) for g in set(genres)) >= 3)
    if repeats and not diversity:
        issues.append("repetitive")
    return issues


def assess(
    profile: Dict, mode: Union[str, ScoringMode], recs: Recommendations, grounded: Set[str],
    catalog_genres: Set[str], catalog_moods: Set[str], dropped: Set[str] = frozenset(), diversity: bool = False,
) -> Assessment:
    """
    `dropped` lists requested fields (e.g. "genre") the agent had to give up on. Dropping a
    requirement makes the remaining match look easy, so it caps confidence below the
    human-review line: the system did NOT deliver what was asked for.
    """
    fit = fit_of(profile, mode, recs)
    evidence = evidence_of(grounded)
    separation = separation_of(profile, mode, recs)
    issues = find_issues(profile, recs, fit, catalog_genres, catalog_moods, diversity)

    confidence = FIT_WEIGHT * fit + EVIDENCE_WEIGHT * evidence + SEPARATION_WEIGHT * separation
    if "genre_not_in_catalog" in issues or "mood_not_in_catalog" in issues:
        confidence -= CATALOG_GAP_PENALTY
    if dropped:
        confidence = min(confidence, DROPPED_CAP)
    confidence = round(_clamp(confidence), 2)
    return Assessment(confidence, label_for(confidence), round(fit, 2), round(evidence, 2),
                      round(separation, 2), issues)
