"""
Tests for the MCP tool handlers in server.py.

server.py runs `bootstrap()` at import time and exits if no rules are loaded.
We sidestep that by patching `loader._DEFAULT_RULES_ROOT` to a temp tree
*before* importing server. Each test imports server fresh via importlib.reload
to get a clean store keyed to its fixture.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _import_server_with_root(tmp_rules_root: Path):
    """(Re)import the server module with rules pointing at tmp_rules_root."""
    import loader

    loader._DEFAULT_RULES_ROOT = tmp_rules_root  # noqa: SLF001
    if "server" in sys.modules:
        del sys.modules["server"]
    return importlib.import_module("server")


@pytest.fixture
def srv(tmp_rules_root: Path):
    return _import_server_with_root(tmp_rules_root)


async def _call(srv, tool_name: str, **arguments):
    return await srv.dispatch_tool(tool_name, arguments)


async def test_list_projects(srv) -> None:
    result = await _call(srv, "list_projects")
    text = result[0].text
    assert "proj-a" in text
    assert "proj-b" in text


async def test_list_rule_docs_no_filter(srv) -> None:
    result = await _call(srv, "list_rule_docs", project="proj-a")
    text = result[0].text
    assert "AGENTS.md" in text
    assert "patterns/foo.md" in text
    assert "skills/bar.md" in text
    assert "workflows/bug-fix.md" in text
    assert "core/guardrails.md" in text


async def test_list_rule_docs_filtered(srv) -> None:
    result = await _call(srv, "list_rule_docs", project="proj-a", doc_type="pattern")
    text = result[0].text
    assert "patterns/foo.md" in text
    assert "skills/bar.md" not in text


async def test_list_rule_docs_unknown_project(srv) -> None:
    result = await _call(srv, "list_rule_docs", project="nope")
    assert "not found" in result[0].text.lower()
    # short error: should not dump the full project list
    assert "list_projects" in result[0].text


async def test_get_agents_md(srv) -> None:
    result = await _call(srv, "get_agents_md", project="proj-a")
    assert "AGENTS.md — Proj A" in result[0].text


async def test_get_agents_md_unknown_project(srv) -> None:
    result = await _call(srv, "get_agents_md", project="nope")
    assert "not found" in result[0].text.lower()


async def test_get_rules_removed(srv) -> None:
    """Breaking change: get_rules is gone in favor of typed fetch tools."""
    result = await _call(srv, "get_rules", project="proj-b", context="error-conventions")
    assert "Unknown tool" in result[0].text


async def test_get_guardrails(srv) -> None:
    result = await _call(srv, "get_guardrails", project="proj-a")
    text = result[0].text
    assert "Guardrails" in text
    assert "MUST do X" in text
    assert "Definition of Done" in text


async def test_get_index(srv) -> None:
    result = await _call(srv, "get_index", project="proj-a")
    assert "INDEX" in result[0].text


async def test_get_architecture_overview(srv) -> None:
    result = await _call(srv, "get_architecture", project="proj-a")
    assert "Architecture — Proj A" in result[0].text


async def test_get_architecture_adr(srv) -> None:
    result = await _call(srv, "get_architecture", project="proj-a", name="0001-pick-foo")
    assert "ADR 0001" in result[0].text


async def test_get_language_rules(srv) -> None:
    result = await _call(srv, "get_language_rules", project="proj-a", language="java")
    text = result[0].text
    assert "Java standards" in text


async def test_get_language_rules_testing_doc(srv) -> None:
    result = await _call(srv, "get_language_rules", project="proj-a", language="java", doc="testing")
    assert "JUnit 5" in result[0].text


async def test_get_language_rules_invalid_doc(srv) -> None:
    result = await _call(srv, "get_language_rules", project="proj-a", language="java", doc="bogus")
    assert "must be one of" in result[0].text


async def test_get_workflow(srv) -> None:
    result = await _call(srv, "get_workflow", project="proj-a", name="bug-fix")
    text = result[0].text
    assert "Reproduce" in text
    # see_also drives Next Calls
    assert "Next Calls" in text
    assert "get_skill" in text
    assert "get_pattern" in text


async def test_get_gate_listing(srv) -> None:
    result = await _call(srv, "get_gate", project="proj-a")
    text = result[0].text
    assert "verify-java.sh" in text
    assert "Available scripts" in text


async def test_get_gate_named(srv) -> None:
    result = await _call(srv, "get_gate", project="proj-a", name="verify-java")
    text = result[0].text
    assert "verify-java.sh" in text
    assert "does not execute" in text


async def test_get_gate_unknown_script(srv) -> None:
    result = await _call(srv, "get_gate", project="proj-a", name="verify-zzz")
    assert "not found" in result[0].text.lower()


async def test_start_task_matches_workflow_via_trigger(srv) -> None:
    result = await _call(
        srv, "start_task", project="proj-a", task="please fix a bug in the route"
    )
    text = result[0].text
    assert "Guardrails" in text
    assert "Definition of Done" in text
    assert "bug-fix" in text
    assert "Next Calls" in text
    assert "get_skill" in text


async def test_start_task_unknown_project(srv) -> None:
    result = await _call(srv, "start_task", project="nope", task="something")
    assert "not found" in result[0].text.lower()


async def test_get_pattern(srv) -> None:
    result = await _call(srv, "get_pattern", project="proj-a", pattern="foo")
    assert "Pattern: Foo" in result[0].text


async def test_get_pattern_missing(srv) -> None:
    result = await _call(srv, "get_pattern", project="proj-a", pattern="zzz")
    assert "not found" in result[0].text.lower()
    assert "list_rule_docs" in result[0].text


async def test_get_skill(srv) -> None:
    result = await _call(srv, "get_skill", project="proj-a", skill="bar")
    assert "Skill: Bar" in result[0].text


async def test_get_skill_missing(srv) -> None:
    result = await _call(srv, "get_skill", project="proj-a", skill="zzz")
    assert "not found" in result[0].text.lower()


async def test_search_rules(srv) -> None:
    result = await _call(srv, "search_rules", query="DLQ flows")
    assert "patterns/foo.md" in result[0].text


async def test_search_rules_empty_query(srv) -> None:
    result = await _call(srv, "search_rules", query="   ")
    assert "must not be empty" in result[0].text


async def test_search_rules_top_k_bounds_clamp(srv) -> None:
    """Bad top_k values are clamped, not crashed on."""
    r1 = await _call(srv, "search_rules", query="agents", top_k=-5)
    r2 = await _call(srv, "search_rules", query="agents", top_k=9999)
    assert r1[0].text  # both should produce non-empty results, no exception
    assert r2[0].text


async def test_unknown_tool(srv) -> None:
    result = await _call(srv, "definitely_not_a_tool")
    assert "Unknown tool" in result[0].text


async def test_get_error_conventions_removed(srv) -> None:
    """Breaking change in 0.2.0: the redundant tool is gone."""
    result = await _call(srv, "get_error_conventions", project="proj-b")
    assert "Unknown tool" in result[0].text
