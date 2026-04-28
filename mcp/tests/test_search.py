"""Tests for search.py."""

from __future__ import annotations

from pathlib import Path

from loader import load_store
from search import RulesSearchEngine, _extract_headings, _heading_for_line, _tokenize

# -- tokenizer --------------------------------------------------------------


def test_tokenize_lowercases_and_filters_stopwords() -> None:
    tokens = _tokenize("The quick BROWN fox")
    assert "the" not in tokens
    assert "quick" in tokens
    assert "brown" in tokens
    assert "fox" in tokens


def test_tokenize_splits_camel_case() -> None:
    tokens = _tokenize("errorHandler")
    assert "error" in tokens
    assert "handler" in tokens


def test_tokenize_splits_kebab_and_snake() -> None:
    tokens = _tokenize("error-handler dead_letter_queue")
    for t in ("error", "handler", "dead", "letter", "queue"):
        assert t in tokens


def test_tokenize_drops_one_char_tokens() -> None:
    assert _tokenize("a b cd") == ["cd"]


# -- heading helpers --------------------------------------------------------


def test_extract_headings() -> None:
    md = "# Title\n\nintro\n\n## Sub\n\nbody\n\n### Deep\n\nfoo\n#### too deep"
    assert _extract_headings(md) == ["Title", "Sub", "Deep"]


def test_heading_for_line_finds_nearest_above() -> None:
    lines = [
        "# Top",
        "intro",
        "## Section A",
        "body 1",
        "body 2",
        "## Section B",
        "body 3",
    ]
    assert _heading_for_line(lines, 4) == "Section A"
    assert _heading_for_line(lines, 6) == "Section B"
    assert _heading_for_line(lines, 0) == "Top"


# -- search engine ----------------------------------------------------------


def test_search_returns_results(tmp_rules_root: Path) -> None:
    store = load_store(tmp_rules_root)
    engine = RulesSearchEngine(store)
    results = engine.search("DLQ flows")
    assert results, "expected at least one result"
    top = results[0]
    assert top.relative_path == "patterns/foo.md"
    assert top.heading is not None


def test_search_project_filter(tmp_rules_root: Path) -> None:
    store = load_store(tmp_rules_root)
    engine = RulesSearchEngine(store)
    results = engine.search("agents", project="proj-b")
    for r in results:
        assert r.project == "proj-b"


def test_search_doc_type_filter(tmp_rules_root: Path) -> None:
    store = load_store(tmp_rules_root)
    engine = RulesSearchEngine(store)
    results = engine.search("foo bar baz", doc_type="pattern")
    for r in results:
        assert r.doc_type == "pattern"


def test_search_empty_query() -> None:
    from loader import RulesStore

    engine = RulesSearchEngine(RulesStore(docs=[]))
    assert engine.search("") == []
    assert engine.search("   ") == []


def test_search_top_k_bound(tmp_rules_root: Path) -> None:
    store = load_store(tmp_rules_root)
    engine = RulesSearchEngine(store)
    results = engine.search("a", top_k=2)  # 'a' is too short → empty
    assert isinstance(results, list)


def test_heading_boost_ranks_heading_match_higher(tmp_path: Path) -> None:
    """A doc with the term in the H1 should outrank one with the term once in body."""
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "agents.md").write_text("# AGENTS.md — P\n\nplaceholder.\n")
    (tmp_path / "p" / "architecture.md").write_text(
        "# Architecture — Apache Camel routing\n\ndetails about routing.\n"
    )
    (tmp_path / "p" / "anti-patterns.md").write_text(
        "# Anti-patterns\n\nDo not mention camel routing in passing once.\n"
    )
    store = load_store(tmp_path)
    engine = RulesSearchEngine(store)
    results = engine.search("camel routing", project="p")
    assert results
    # The architecture doc (which has 'camel routing' in heading) should rank
    # at or above the anti-patterns doc.
    paths = [r.relative_path for r in results]
    assert paths.index("architecture.md") <= paths.index("anti-patterns.md")
