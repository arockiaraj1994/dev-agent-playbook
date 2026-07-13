"""
Tests for the MCP tool handlers in server.py.

server.py loads corpora at import time. We point MCP_STANDARDS_ROOT (and an
empty MCP_REQUIREMENTS_ROOT) at a temp tree *before* importing server, and
reload corpus/loader/cache/server so the bootstrap picks up the fixture.
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path

import pytest


def _import_server_with_root(tmp_rules_root: Path):
    """(Re)import the server module with standards pointing at tmp_rules_root."""
    empty_req = tmp_rules_root / "_empty_requirements"
    empty_req.mkdir(exist_ok=True)
    os.environ["MCP_STANDARDS_ROOT"] = str(tmp_rules_root)
    os.environ["MCP_REQUIREMENTS_ROOT"] = str(empty_req)

    # Drop cached modules so corpus specs and bootstrap re-read env.
    for mod in (
        "server",
        "cache",
        "corpus",
        "loader",
        "search",
        "tools.start_task",
        "tools.search_tool",
        "tools.docs",
        "tools.projects",
        "tools.requirements",
    ):
        sys.modules.pop(mod, None)

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


async def test_find_rules_list_mode(srv) -> None:
    result = await _call(srv, "find_rules", project="proj-a")
    text = result[0].text
    assert "AGENTS.md" in text
    assert "patterns/foo.md" in text
    assert "skills/bar.md" in text
    assert "workflows/bug-fix.md" in text
    assert "core/guardrails.md" in text


async def test_find_rules_list_mode_surfaces_triggers(srv) -> None:
    # This is what makes dropping get_index lossless.
    result = await _call(srv, "find_rules", project="proj-a")
    text = result[0].text
    assert "Triggers:" in text
    assert "fix a bug" in text


async def test_find_rules_filtered(srv) -> None:
    result = await _call(srv, "find_rules", project="proj-a", doc_type="pattern")
    text = result[0].text
    assert "patterns/foo.md" in text
    assert "skills/bar.md" not in text


async def test_find_rules_unknown_project(srv) -> None:
    result = await _call(srv, "find_rules", project="nope")
    assert "not found" in result[0].text.lower()
    # short error: should not dump the full project list
    assert "list_projects" in result[0].text


async def test_get_agents_md(srv) -> None:
    result = await _call(srv, "get_doc", kind="agents", project="proj-a")
    assert "AGENTS.md - Proj A" in result[0].text


async def test_get_agents_md_chains_to_start_task(srv) -> None:
    """The dead end that made get_agents_md the most-called tool: it used to
    return no Next Calls at all, so the agent had nowhere to go."""
    result = await _call(srv, "get_doc", kind="agents", project="proj-a")
    text = result[0].text
    assert "## Next Calls" in text
    assert 'start_task(project="proj-a"' in text
    assert "START HERE" in text


async def test_get_agents_md_unknown_project(srv) -> None:
    result = await _call(srv, "get_doc", kind="agents", project="nope")
    assert "not found" in result[0].text.lower()


async def test_get_rules_removed(srv) -> None:
    """Breaking change: get_rules is gone in favor of typed fetch tools."""
    result = await _call(srv, "get_rules", project="proj-b", context="error-conventions")
    assert "Unknown tool" in result[0].text


async def test_get_guardrails(srv) -> None:
    result = await _call(srv, "get_doc", kind="guardrails", project="proj-a")
    text = result[0].text
    assert "Guardrails" in text
    assert "MUST do X" in text
    assert "Definition of Done" in text


async def test_get_index_removed(srv) -> None:
    """Breaking change: get_index folded into find_rules list mode, which now
    surfaces the same `triggers:` map."""
    result = await _call(srv, "get_index", project="proj-a")
    assert "Unknown tool" in result[0].text


async def test_get_architecture_overview(srv) -> None:
    result = await _call(srv, "get_doc", kind="architecture", project="proj-a")
    assert "Architecture - Proj A" in result[0].text


async def test_get_architecture_adr(srv) -> None:
    result = await _call(
        srv, "get_doc", kind="architecture", project="proj-a", name="0001-pick-foo"
    )
    assert "ADR 0001" in result[0].text


async def test_get_language_rules(srv) -> None:
    result = await _call(srv, "get_doc", kind="language", project="proj-a", name="java")
    text = result[0].text
    assert "Java standards" in text


async def test_get_language_rules_testing_doc(srv) -> None:
    result = await _call(
        srv, "get_doc", kind="language", project="proj-a", name="java", doc="testing"
    )
    assert "JUnit 5" in result[0].text


async def test_get_language_rules_invalid_doc(srv) -> None:
    result = await _call(
        srv, "get_doc", kind="language", project="proj-a", name="java", doc="bogus"
    )
    assert "must be one of" in result[0].text


async def test_get_workflow(srv) -> None:
    result = await _call(srv, "get_doc", kind="workflow", project="proj-a", name="bug-fix")
    text = result[0].text
    assert "Reproduce" in text
    # see_also drives Next Calls via get_doc
    assert "Next Calls" in text
    assert 'kind="skill"' in text
    assert 'kind="pattern"' in text


async def test_see_also_core_kind_renders(srv) -> None:
    """`core:guardrails` used to be silently dropped by _format_call, so three
    real nexre workflows shipped with a Next Call that rendered nothing."""
    result = await _call(srv, "get_doc", kind="workflow", project="proj-a", name="bug-fix")
    assert 'get_doc(project="proj-a", kind="guardrails")' in result[0].text


async def test_see_also_gates_alias_renders(srv) -> None:
    """Same bug, plural spelling: `gates:README` rendered nothing."""
    result = await _call(srv, "get_doc", kind="skill", project="proj-a", name="bar")
    assert 'get_doc(project="proj-a", kind="gate")' in result[0].text


async def test_get_gate_listing(srv) -> None:
    result = await _call(srv, "get_doc", kind="gate", project="proj-a")
    text = result[0].text
    assert "verify-java.sh" in text
    assert "Available scripts" in text


async def test_get_gate_named(srv) -> None:
    result = await _call(srv, "get_doc", kind="gate", project="proj-a", name="verify-java")
    text = result[0].text
    assert "verify-java.sh" in text
    assert "does not execute" in text


async def test_get_gate_named_shows_script_body(srv) -> None:
    """The description promises the script's first lines; it used to show only
    the path."""
    result = await _call(srv, "get_doc", kind="gate", project="proj-a", name="verify-java")
    assert "echo ok" in result[0].text


async def test_get_gate_unknown_script(srv) -> None:
    result = await _call(srv, "get_doc", kind="gate", project="proj-a", name="verify-zzz")
    assert "not found" in result[0].text.lower()


async def test_start_task_matches_workflow_via_trigger(srv) -> None:
    result = await _call(srv, "start_task", project="proj-a", task="please fix a bug in the route")
    text = result[0].text
    assert "Guardrails" in text
    assert "Definition of Done" in text
    assert "bug-fix" in text
    assert "Next Calls" in text
    assert 'kind="skill"' in text


async def test_start_task_inlines_identity(srv) -> None:
    """start_task subsumes the one part of AGENTS.md it did not already cover,
    so there is no reason left to call get_doc(kind=agents) first."""
    result = await _call(srv, "start_task", project="proj-a", task="fix a bug")
    text = result[0].text
    assert "senior proj-a engineer" in text
    # ...but not the rest of AGENTS.md, which just restates the guardrails.
    assert "errorHandler boundaries" not in text


async def test_start_task_unknown_project(srv) -> None:
    result = await _call(srv, "start_task", project="nope", task="something")
    assert "not found" in result[0].text.lower()


async def test_start_task_project_optional_disambiguates(srv) -> None:
    """Fixture has two projects - omitting project must ask which one."""
    result = await _call(srv, "start_task", task="fix a bug")
    text = result[0].text.lower()
    assert "which project" in text
    assert "proj-a" in text
    assert "proj-b" in text


async def test_get_doc_project_optional_disambiguates(srv) -> None:
    result = await _call(srv, "get_doc", kind="guardrails")
    text = result[0].text.lower()
    assert "which project" in text


async def test_get_pattern(srv) -> None:
    result = await _call(srv, "get_doc", kind="pattern", project="proj-a", name="foo")
    assert "Pattern: Foo" in result[0].text


async def test_get_pattern_missing(srv) -> None:
    result = await _call(srv, "get_doc", kind="pattern", project="proj-a", name="zzz")
    assert "not found" in result[0].text.lower()
    assert "find_rules" in result[0].text


async def test_get_skill(srv) -> None:
    result = await _call(srv, "get_doc", kind="skill", project="proj-a", name="bar")
    assert "Skill: Bar" in result[0].text


async def test_get_skill_missing(srv) -> None:
    result = await _call(srv, "get_doc", kind="skill", project="proj-a", name="zzz")
    assert "not found" in result[0].text.lower()


async def test_get_doc_requires_name_for_pattern(srv) -> None:
    result = await _call(srv, "get_doc", kind="pattern", project="proj-a")
    assert "name" in result[0].text.lower()


async def test_legacy_get_pattern_removed(srv) -> None:
    result = await _call(srv, "get_pattern", project="proj-a", pattern="foo")
    assert "Unknown tool" in result[0].text


async def test_find_rules_search_mode(srv) -> None:
    result = await _call(srv, "find_rules", project="proj-a", query="DLQ flows")
    assert "patterns/foo.md" in result[0].text


async def test_find_rules_blank_query_falls_back_to_list(srv) -> None:
    """A whitespace-only query is a listing request, not an error."""
    result = await _call(srv, "find_rules", project="proj-a", query="   ")
    assert "patterns/foo.md" in result[0].text


async def test_find_rules_top_k_bounds_clamp(srv) -> None:
    """Bad top_k values are clamped, not crashed on."""
    r1 = await _call(srv, "find_rules", project="proj-a", query="agents", top_k=-5)
    r2 = await _call(srv, "find_rules", project="proj-a", query="agents", top_k=9999)
    assert r1[0].text  # both should produce non-empty results, no exception
    assert r2[0].text


async def test_search_rules_removed(srv) -> None:
    """Breaking change: search_rules merged into find_rules query mode."""
    result = await _call(srv, "search_rules", query="DLQ flows")
    assert "Unknown tool" in result[0].text


async def test_unknown_tool(srv) -> None:
    result = await _call(srv, "definitely_not_a_tool")
    assert "Unknown tool" in result[0].text


# ---------------------------------------------------------------------------
# Tool surface
# ---------------------------------------------------------------------------


async def test_tool_surface_is_read_only(srv) -> None:
    tools = await srv.list_tools()
    # 6 tools: start_task, list_projects, find_rules, get_doc,
    # list_requirements, start_requirement
    assert len(tools) == 6
    names = {t.name for t in tools}
    assert names == {
        "start_task",
        "list_projects",
        "find_rules",
        "get_doc",
        "list_requirements",
        "start_requirement",
    }
    for t in tools:
        assert t.annotations is not None, f"{t.name} has no annotations"
        assert t.annotations.readOnlyHint is True, t.name
        assert t.annotations.openWorldHint is False, t.name


async def test_exactly_one_tool_claims_to_be_first(srv) -> None:
    """start_task is the coding entry point. start_requirement is PM-only and
    must not use the same 'call this first' phrasing or agents get confused."""
    directive = re.compile(r"call (this|it) first", re.IGNORECASE)
    tools = await srv.list_tools()
    claimants = [t.name for t in tools if directive.search(t.description or "")]
    assert claimants == ["start_task"]


async def test_get_error_conventions_removed(srv) -> None:
    """Breaking change in 0.2.0: the redundant tool is gone."""
    result = await _call(srv, "get_error_conventions", project="proj-b")
    assert "Unknown tool" in result[0].text


def test_format_call_renders_get_doc_for_all_kinds() -> None:
    """Every see_also / targets kind must render a get_doc (or entry-point) call."""
    from tools.docs import _format_call

    project = "nexre"
    cases = [
        ("pattern", "repository", 'kind="pattern"', 'name="repository"'),
        ("skill", "add-screen", 'kind="skill"', 'name="add-screen"'),
        ("workflow", "bug-fix", 'kind="workflow"', 'name="bug-fix"'),
        ("gate", "README", 'kind="gate"', None),
        ("gates", "verify-java", 'kind="gate"', 'name="verify-java"'),
        ("language", "kotlin", 'kind="language"', 'name="kotlin"'),
        ("language", "kotlin/testing", 'kind="language"', 'doc="testing"'),
        ("architecture", "overview", 'kind="architecture"', None),
        ("architecture", "0001-foo", 'kind="architecture"', 'name="0001-foo"'),
        ("core", "guardrails", 'kind="guardrails"', None),
        ("requirement", "ST-101", 'kind="requirement"', 'name="ST-101"'),
        ("agents", "AGENTS", 'kind="agents"', None),
        ("tool", "start_task", "start_task(", None),
        ("tool", "get_guardrails", 'kind="guardrails"', None),
        ("tool", "find_rules", "find_rules(", None),
        ("tool", "list_projects", "list_projects()", None),
    ]
    for kind, name, must_contain, also in cases:
        rendered = _format_call(kind, project, name)
        assert rendered, f"{kind}:{name} rendered nothing"
        assert must_contain in rendered, f"{kind}:{name} → {rendered}"
        if also:
            assert also in rendered, f"{kind}:{name} missing {also} in {rendered}"
        if kind != "tool" or name not in ("start_task", "find_rules", "list_projects"):
            assert "get_doc" in rendered or "start_task" in rendered or "find_rules" in rendered or "list_projects" in rendered
