"""Tests for loader.py."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from loader import (
    _infer_doc_type,
    _is_excluded,
    _parse_docs,
    _parse_frontmatter,
    load_store,
)

# -- _infer_doc_type --------------------------------------------------------


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("agents.md", "agents"),
        ("architecture.md", "architecture"),
        ("error-conventions.md", "error-conventions"),
        ("anti-patterns.md", "anti-patterns"),
        ("glossary.md", "glossary"),
        ("patterns/quarkus.md", "pattern"),
        ("patterns/nested/dir/foo.md", "pattern"),
        ("skills/add-connector.md", "skill"),
        ("misc/readme.md", "other"),
        ("random.md", "other"),
    ],
)
def test_infer_doc_type(rel: str, expected: str) -> None:
    assert _infer_doc_type(rel) == expected


# -- _is_excluded -----------------------------------------------------------


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("README.md", True),
        ("CONTRIBUTING.md", True),
        ("TEMPLATE.md", True),
        ("CHANGELOG.md", True),
        ("mcp/server.py", True),
        (".git/HEAD", True),
        (".github/workflows/ci.yml", True),
        ("scripts/validate-rules.py", True),
        ("integration-manager/agents.md", False),
        ("baton-sso-config/patterns/foo.md", False),
    ],
)
def test_is_excluded(rel: str, expected: bool) -> None:
    assert _is_excluded(rel) is expected


# -- _parse_frontmatter -----------------------------------------------------


def test_frontmatter_none() -> None:
    md, body = _parse_frontmatter("# Title\n\nBody")
    assert md == {}
    assert body == "# Title\n\nBody"


def test_frontmatter_basic() -> None:
    raw = (
        '---\ntitle: Hello\ndescription: A test doc\ntags: [a, b, "c d"]\n---\n# Title\nBody line\n'
    )
    md, body = _parse_frontmatter(raw)
    assert md["title"] == "Hello"
    assert md["description"] == "A test doc"
    assert md["tags"] == ["a", "b", "c d"]
    assert body == "# Title\nBody line\n"


def test_frontmatter_quoted_strings() -> None:
    raw = "---\ntitle: 'hello world'\nname: \"foo\"\n---\nbody"
    md, _ = _parse_frontmatter(raw)
    assert md["title"] == "hello world"
    assert md["name"] == "foo"


def test_frontmatter_unterminated() -> None:
    """Missing closing `---` -> treat the whole content as body, no metadata."""
    raw = "---\ntitle: Hello\nno close\n# body"
    md, body = _parse_frontmatter(raw)
    assert md == {}
    assert body == raw


def test_frontmatter_empty_value() -> None:
    raw = "---\ntitle:\n---\nbody"
    md, _ = _parse_frontmatter(raw)
    assert md["title"] == ""


def test_frontmatter_ignores_comment_lines() -> None:
    raw = "---\n# this is a comment\ntitle: Hello\n---\nbody"
    md, _ = _parse_frontmatter(raw)
    assert md == {"title": "Hello"}


# -- _parse_docs / load_store -----------------------------------------------


def test_parse_docs_loads_expected_files(tmp_rules_root: Path) -> None:
    docs = _parse_docs(tmp_rules_root)
    rels = {(d.project, d.relative_path) for d in docs}
    assert ("proj-a", "agents.md") in rels
    assert ("proj-a", "architecture.md") in rels
    assert ("proj-a", "patterns/foo.md") in rels
    assert ("proj-a", "skills/bar.md") in rels
    assert ("proj-b", "agents.md") in rels
    assert ("proj-b", "error-conventions.md") in rels
    assert ("proj-b", "stray.md") in rels


def test_parse_docs_excludes_top_level_readme(tmp_rules_root: Path) -> None:
    docs = _parse_docs(tmp_rules_root)
    paths = [d.relative_path for d in docs]
    assert "README.md" not in paths


def test_parse_docs_warns_on_loose_top_level(
    tmp_rules_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        _parse_docs(tmp_rules_root)
    assert any("loose.md" in r.message for r in caplog.records)


def test_parse_docs_warns_on_other_doc_type(
    tmp_rules_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        _parse_docs(tmp_rules_root)
    assert any("stray.md" in r.message for r in caplog.records)


def test_parse_docs_strips_frontmatter_from_content(tmp_rules_root: Path) -> None:
    docs = _parse_docs(tmp_rules_root)
    proj_a_agents = next(
        d for d in docs if d.project == "proj-a" and d.relative_path == "agents.md"
    )
    assert not proj_a_agents.content.startswith("---")
    assert proj_a_agents.metadata["title"] == "Proj A agents"
    assert proj_a_agents.metadata["tags"] == ["stack-a", "rest"]


def test_load_store_projects_and_lookups(tmp_rules_root: Path) -> None:
    store = load_store(tmp_rules_root)
    assert store.projects() == ["proj-a", "proj-b"]
    assert store.get("proj-a", "agents.md") is not None
    assert store.get("proj-a", "missing.md") is None
    patterns = store.of_type("proj-a", "pattern")
    assert {d.name for d in patterns} == {"foo"}
    skills = store.of_type("proj-a", "skill")
    assert {d.name for d in skills} == {"bar"}
