"""
Guardrails for the music agent: check inputs before work starts, and sanity-check
the profile before it is used. Failures raise GuardrailError, which carries a
short code (for logs and tests) and a friendly message (for the user).

Honest scope: the injection filter is a small pattern list, not a security
boundary. The real protection is structural: request text is only ever used for
keyword lookup, never executed, never sent to a model, and never used to build
a file path or command.
"""

import logging
import re
from typing import Dict, List, Sequence, Tuple

log = logging.getLogger("musicagent.guardrails")

MAX_REQUEST_CHARS = 300

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier)",
    r"(reveal|show|print|leak)\s+.{0,30}(system\s+prompt|api[\s_-]?key|password|secret)",
    r"system\s+prompt",
    r"api[\s_-]?key",
    r"you\s+are\s+now\b",
    r"<\s*/?\s*script",
    r"\b(drop\s+table|rm\s+-rf)\b",
]
_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


class GuardrailError(ValueError):
    """Raised when a request or profile fails a safety check."""

    def __init__(self, code: str, user_message: str):
        super().__init__(f"{code}: {user_message}")
        self.code = code
        self.user_message = user_message


def validate_request(text: object) -> str:
    """Return a cleaned request string, or raise GuardrailError explaining why it was refused."""
    if not isinstance(text, str):
        raise GuardrailError("not_text", "The request must be text.")

    cleaned = CONTROL_CHARS_RE.sub(" ", text)
    cleaned = " ".join(cleaned.split())  # collapse whitespace and newlines

    if not cleaned:
        raise GuardrailError(
            "empty_request",
            "Please describe what you want to hear, e.g. 'chill music for studying'.",
        )
    if len(cleaned) > MAX_REQUEST_CHARS:
        raise GuardrailError(
            "too_long",
            f"That request is {len(cleaned)} characters; please keep it under {MAX_REQUEST_CHARS}.",
        )
    if not any(ch.isalpha() for ch in cleaned):
        raise GuardrailError("no_letters", "I could not find any words in that request.")
    for pattern in _INJECTION_RE:
        if pattern.search(cleaned):
            raise GuardrailError(
                "unsafe_request",
                "That looks like an instruction to the system rather than a music request, so I skipped it.",
            )
    return cleaned


def validate_catalog(songs: Sequence[Dict]) -> None:
    """Refuse to run on an empty catalog."""
    if not songs:
        raise GuardrailError("empty_catalog", "The song catalog is empty, so there is nothing to recommend.")


def validate_profile(profile: Dict) -> Tuple[Dict, List[str]]:
    """Clamp numeric preferences into range. Returns (clean profile, list of corrections made)."""
    clean = dict(profile)
    corrections: List[str] = []

    energy = float(clean.get("target_energy", 0.5))
    if not 0.0 <= energy <= 1.0:
        clamped = min(1.0, max(0.0, energy))
        corrections.append(f"target_energy {energy:.2f} out of range, clamped to {clamped:.2f}")
        energy = clamped
    clean["target_energy"] = round(energy, 2)

    for key in ("favorite_genre", "favorite_mood", "preferred_detailed_mood"):
        value = clean.get(key)
        if value is not None:
            clean[key] = str(value).strip().lower() or None

    for correction in corrections:
        log.warning("profile corrected: %s", correction)
    return clean, corrections
