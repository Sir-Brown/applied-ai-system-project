"""
Offline retriever for the music agent (the "R" in RAG).

It indexes two sources:
  1. Glossary documents in data/knowledge/*.md (activities, moods, genres, modifiers)
  2. The song catalog itself (its genres, moods and detailed moods)

Given a plain-English request it returns the matching "chunks". The planner then
turns those chunks into a taste profile, so retrieval directly changes what the
system recommends. Matching is simple keyword overlap on purpose: it is fast,
needs no model or API key, gives the same answer every time, and every match can
be explained to the user.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger("musicagent.retriever")

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"

# Later kinds override earlier kinds when they set the same profile field, so an
# explicit genre ("jazz") beats a genre implied by an activity ("studying").
KIND_PRIORITY = {"activity": 0, "mood": 1, "genre": 2, "modifier": 3}

TOKEN_RE = re.compile(r"[a-z0-9&'-]+")
CLAUSE_SPLIT_RE = re.compile(r"[,;.!?\n]+| but | and then ")
NEGATIONS = {"no", "not", "nothing", "without", "never", "dont", "don't", "avoid", "non", "except"}
NEGATION_WINDOW = 3  # how many words before a keyword may negate it

BOOL_FIELDS = {"acoustic", "instrumental", "diverse", "negatable"}
FLOAT_FIELDS = {"energy", "energy_delta"}
INT_FIELDS = {"decade"}
STR_FIELDS = {"genre", "mood", "detailed_mood"}
KNOWN_FIELDS = BOOL_FIELDS | FLOAT_FIELDS | INT_FIELDS | STR_FIELDS | {"kind", "keywords", "note"}


@dataclass
class Chunk:
    """One retrievable document: some trigger keywords plus the profile fields it sets."""
    title: str
    kind: str                       # activity | mood | genre | modifier
    keywords: Tuple[str, ...]
    fields: Dict[str, object]       # e.g. {"genre": "lofi", "energy": 0.4}
    source: str                     # file name, or "catalog"
    negatable: bool = False
    note: str = ""


@dataclass
class Hit:
    """A chunk that matched the request."""
    chunk: Chunk
    score: float
    matched: List[str] = field(default_factory=list)
    negated: bool = False


def stem(word: str) -> str:
    """Very small stemmer so 'studying' matches 'study' and 'beats' matches 'beat'."""
    if word in NEGATIONS:  # "nothing" must stay "nothing", or negation detection breaks
        return word
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> List[str]:
    """Lowercase, split into word tokens (keeps &, ' and - inside words), then stem."""
    return [stem(t) for t in TOKEN_RE.findall(text.lower())]


def _parse_value(key: str, raw: str):
    raw = raw.strip()
    if key in BOOL_FIELDS:
        if raw.lower() not in {"yes", "no"}:
            raise ValueError(f"{key} must be yes or no, got {raw!r}")
        return raw.lower() == "yes"
    if key in FLOAT_FIELDS:
        return float(raw)
    if key in INT_FIELDS:
        return int(raw)
    return raw


def parse_knowledge_text(text: str, source: str) -> List[Chunk]:
    """Parse a glossary file. Malformed sections are skipped with a warning, never fatal."""
    chunks: List[Chunk] = []
    sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]  # [0] is the file preamble
    for section in sections:
        title, _, body = section.partition("\n")
        title = title.strip()
        values: Dict[str, object] = {}
        try:
            for line in body.splitlines():
                if ":" not in line:
                    continue
                key, _, raw = line.partition(":")
                key = key.strip().lower()
                if key not in KNOWN_FIELDS:
                    log.warning("%s: unknown field %r in section %r (ignored)", source, key, title)
                    continue
                values[key] = raw.strip() if key in {"kind", "keywords", "note"} else _parse_value(key, raw)
            kind = str(values.pop("kind", ""))
            if kind not in KIND_PRIORITY:
                raise ValueError(f"kind must be one of {sorted(KIND_PRIORITY)}, got {kind!r}")
            keywords = tuple(k.strip().lower() for k in str(values.pop("keywords", "")).split(",") if k.strip())
            if not keywords:
                raise ValueError("no keywords")
        except ValueError as exc:
            log.warning("%s: skipping section %r: %s", source, title, exc)
            continue
        negatable = bool(values.pop("negatable", False))
        note = str(values.pop("note", ""))
        chunks.append(Chunk(title, kind, keywords, values, source, negatable, note))
    return chunks


def load_knowledge(directory: Path = KNOWLEDGE_DIR) -> List[Chunk]:
    """Load every *.md glossary in a directory. A missing directory yields no chunks."""
    chunks: List[Chunk] = []
    if not Path(directory).is_dir():
        log.warning("knowledge directory not found: %s (retrieval will use the catalog only)", directory)
        return chunks
    for path in sorted(Path(directory).glob("*.md")):
        chunks.extend(parse_knowledge_text(path.read_text(encoding="utf-8"), path.name))
    log.info("loaded %d glossary chunks from %s", len(chunks), directory)
    return chunks


def chunks_from_catalog(songs: Iterable[Dict]) -> List[Chunk]:
    """Second data source: the catalog's own genres, moods and detailed moods."""
    seen = {"genre": set(), "mood": set(), "detailed_mood": set()}
    for song in songs:
        for key in seen:
            value = (song.get(key) or "").strip().lower()
            if value:
                seen[key].add(value)
    chunks = []
    for key, kind in (("genre", "genre"), ("mood", "mood"), ("detailed_mood", "mood")):
        for value in sorted(seen[key]):
            chunks.append(Chunk(f"catalog {key}: {value}", kind, (value,), {key: value}, "catalog"))
    return chunks


class Retriever:
    """Keyword retriever over a list of chunks, with simple negation handling."""

    def __init__(self, chunks: Sequence[Chunk]):
        self.chunks = list(chunks)
        self._index = [
            (chunk, [(kw, [stem(t) for t in TOKEN_RE.findall(kw)]) for kw in chunk.keywords])
            for chunk in self.chunks
        ]

    def search(self, text: str) -> List[Hit]:
        """Return every chunk whose keywords appear in the text, best match first."""
        clauses = [tokenize(c) for c in CLAUSE_SPLIT_RE.split(text.lower()) if c and c.strip()]
        hits: List[Hit] = []
        for chunk, keyword_tokens in self._index:
            matched: List[str] = []
            positive = 0.0
            negated_only = True
            for kw, kw_tokens in keyword_tokens:
                if not kw_tokens:
                    continue
                for tokens in clauses:
                    for start in _find(tokens, kw_tokens):
                        window = tokens[max(0, start - NEGATION_WINDOW):start]
                        is_negated = any(w in NEGATIONS for w in window)
                        matched.append(kw)
                        positive = max(positive, float(len(kw_tokens)))
                        negated_only = negated_only and is_negated
            if matched:
                unique = sorted(set(matched))
                hits.append(Hit(chunk, positive + 0.5 * (len(unique) - 1), unique, negated_only))
        hits.sort(key=lambda h: (-h.score, h.chunk.title))
        return hits


def _find(tokens: List[str], needle: List[str]) -> List[int]:
    """Start positions where the token sequence `needle` occurs in `tokens`."""
    n = len(needle)
    return [i for i in range(len(tokens) - n + 1) if tokens[i:i + n] == needle]


def build_retriever(
    songs: Iterable[Dict], knowledge_dir: Optional[Path] = None, use_glossary: bool = True,
) -> Retriever:
    """Build a retriever over the catalog, plus the glossary docs when use_glossary is True."""
    chunks = chunks_from_catalog(list(songs))
    if use_glossary:
        chunks += load_knowledge(knowledge_dir or KNOWLEDGE_DIR)
    return Retriever(chunks)
