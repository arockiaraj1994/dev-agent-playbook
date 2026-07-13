"""Unit tests for project resolution (cwd basename / case-insensitive)."""

from __future__ import annotations

from pathlib import Path

from loader import load_store
from tools.docs import _canonical_project, _resolve_project


def test_canonical_project_exact_and_casefold() -> None:
    known = ["nexre", "apache-camel"]
    assert _canonical_project("nexre", known) == "nexre"
    assert _canonical_project("NexRe", known) == "nexre"
    assert _canonical_project("NEXRE", known) == "nexre"
    assert _canonical_project("apache-camel", known) == "apache-camel"
    assert _canonical_project("Apache-Camel", known) == "apache-camel"
    assert _canonical_project("missing", known) is None


def test_resolve_project_case_insensitive_cwd_basename(tmp_rules_root: Path) -> None:
    store = load_store(tmp_rules_root)
    got = _resolve_project(store, "Proj-A")
    assert got.ok
    assert got.project == "proj-a"


def test_resolve_project_omitted_many_mentions_workspace_basename(
    tmp_rules_root: Path,
) -> None:
    store = load_store(tmp_rules_root)
    got = _resolve_project(store, None)
    assert got.status == "needs_project"
    assert got.error_text is not None
    assert "basename of your current workspace" in got.error_text


def test_resolve_project_unknown_mentions_workspace_basename(
    tmp_rules_root: Path,
) -> None:
    store = load_store(tmp_rules_root)
    got = _resolve_project(store, "dev-agent-playbook")
    assert got.status == "not_found"
    assert got.error_text is not None
    assert "basename of your current workspace" in got.error_text
