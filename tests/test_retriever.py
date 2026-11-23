from pathlib import Path

from src.recommender import load_songs
from src.retriever import (
    build_retriever, chunks_from_catalog, load_knowledge, parse_knowledge_text, stem, tokenize,
)

SONGS = load_songs(str(Path(__file__).resolve().parent.parent / "data" / "songs.csv"))


def titles(hits):
    return {h.chunk.title for h in hits}


def test_stemmer_matches_common_word_forms():
    assert stem("studying") == "study"
    assert tokenize("beats")[0] == tokenize("beat")[0]
    assert tokenize("jazz") == ["jazz"]  # words ending in z/ss are left alone
    assert tokenize("Lo-Fi R&B") == ["lo-fi", "r&b"]


def test_parse_knowledge_text_reads_fields_and_types():
    text = "# preamble\n\n## Gym\nkind: activity\nkeywords: gym, lifting\ngenre: pop\nenergy: 0.9\nacoustic: no\n"
    (chunk,) = parse_knowledge_text(text, "test.md")
    assert chunk.keywords == ("gym", "lifting")
    assert chunk.fields == {"genre": "pop", "energy": 0.9, "acoustic": False}


def test_parse_knowledge_text_skips_bad_sections_without_crashing():
    text = (
        "## Bad energy\nkind: activity\nkeywords: x\nenergy: loud\n\n"
        "## No keywords\nkind: mood\nmood: happy\n\n"
        "## Bad kind\nkind: nonsense\nkeywords: y\n\n"
        "## Good\nkind: mood\nkeywords: happy\nmood: happy\n"
    )
    chunks = parse_knowledge_text(text, "test.md")
    assert [c.title for c in chunks] == ["Good"]


def test_shipped_glossaries_all_parse():
    chunks = load_knowledge()
    assert len(chunks) >= 50
    assert {c.kind for c in chunks} == {"activity", "mood", "genre", "modifier"}


def test_missing_knowledge_dir_returns_empty(tmp_path):
    assert load_knowledge(tmp_path / "nope") == []


def test_catalog_chunks_cover_catalog_vocabulary():
    genres = {c.fields["genre"] for c in chunks_from_catalog(SONGS) if "genre" in c.fields}
    assert {"lofi", "pop", "indie pop", "hip hop"} <= genres


def test_retrieval_finds_activity_words_the_catalog_alone_cannot():
    with_docs = build_retriever(SONGS).search("something for studying")
    catalog_only = build_retriever(SONGS, use_glossary=False).search("something for studying")
    assert "Studying" in titles(with_docs)
    assert catalog_only == []


def test_multiword_keywords_beat_their_parts():
    hits = build_retriever(SONGS).search("indie pop please")
    assert hits[0].chunk.fields.get("genre") == "indie pop"


def test_negation_is_detected_per_clause():
    hits = {h.chunk.title: h for h in build_retriever(SONGS).search("no metal, rock please")}
    assert hits["Metal"].negated is True
    assert hits["Rock"].negated is False


def test_negation_survives_filler_words():
    hits = {h.chunk.title: h for h in build_retriever(SONGS).search("nothing too loud")}
    assert hits["Louder"].negated is True


def test_gibberish_matches_nothing():
    assert build_retriever(SONGS).search("asdf qwerty zxcv") == []
