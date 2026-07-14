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
        "tools.requirements",
    ):
        sys.modules.pop(mod, None)

    return importlib.import_module("server")


@pytest.fixture
def srv(tmp_rules_root: Path):
    return _import_server_with_root(tmp_rules_root)


async def _call(srv, tool_name: str, **arguments):
    return await srv.dispatch_tool(tool_name, arguments)


async def test_list_projects_removed(srv) -> None:
    """Breaking change in 0.7.0: project lists live in the resolution errors."""
    result = await _call(srv, "list_projects")
    assert "Unknown tool" in result[0].text


async def test_search_docs_list_mode(srv) -> None:
    result = await _call(srv, "playbook_search_docs", project="proj-a")
    text = result[0].text
    assert "AGENTS.md" in text
    assert "patterns/foo.md" in text
    assert "skills/bar.md" in text
    assert "workflows/bug-fix.md" in text
    assert "core/guardrails.md" in text


async def test_search_docs_list_mode_surfaces_triggers(srv) -> None:
    # This is what makes dropping get_index lossless.
    result = await _call(srv, "playbook_search_docs", project="proj-a")
    text = result[0].text
    assert "Triggers:" in text
    assert "fix a bug" in text


async def test_search_docs_filtered(srv) -> None:
    result = await _call(srv, "playbook_search_docs", project="proj-a", doc_type="pattern")
    text = result[0].text
    assert "patterns/foo.md" in text
    assert "skills/bar.md" not in text


async def test_search_docs_unknown_project_lists_available(srv) -> None:
    result = await _call(srv, "playbook_search_docs", project="nope")
    text = result[0].text
    assert "not found" in text.lower()
    # The error itself teaches the valid projects (list_projects is gone).
    assert "proj-a" in text
    assert "proj-b" in text


async def test_get_agents_md(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="agents", project="proj-a")
    assert "AGENTS.md - Proj A" in result[0].text


async def test_get_agents_md_chains_to_start_task(srv) -> None:
    """The dead end that made get_agents_md the most-called tool: it used to
    return no Next Calls at all, so the agent had nowhere to go."""
    result = await _call(srv, "playbook_get_doc", kind="agents", project="proj-a")
    text = result[0].text
    assert "## Next Calls" in text
    assert 'playbook_start_task(project="proj-a"' in text
    assert "START HERE" in text


async def test_get_agents_md_unknown_project(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="agents", project="nope")
    assert "not found" in result[0].text.lower()


async def test_get_rules_removed(srv) -> None:
    """Breaking change: get_rules is gone in favor of typed fetch tools."""
    result = await _call(srv, "get_rules", project="proj-b", context="error-conventions")
    assert "Unknown tool" in result[0].text


async def test_get_guardrails(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="guardrails", project="proj-a")
    text = result[0].text
    assert "Guardrails" in text
    assert "MUST do X" in text
    assert "Definition of Done" in text


async def test_get_index_removed(srv) -> None:
    """Breaking change: get_index folded into playbook_search_docs list mode,
    which now surfaces the same `triggers:` map."""
    result = await _call(srv, "get_index", project="proj-a")
    assert "Unknown tool" in result[0].text


async def test_get_architecture_overview(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="architecture", project="proj-a")
    assert "Architecture - Proj A" in result[0].text


async def test_get_architecture_adr(srv) -> None:
    result = await _call(
        srv, "playbook_get_doc", kind="architecture", project="proj-a", name="0001-pick-foo"
    )
    assert "ADR 0001" in result[0].text


async def test_get_language_rules(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="language", project="proj-a", name="java")
    text = result[0].text
    assert "Java standards" in text


async def test_get_language_rules_testing_section(srv) -> None:
    result = await _call(
        srv, "playbook_get_doc", kind="language", project="proj-a", name="java", section="testing"
    )
    assert "JUnit 5" in result[0].text


async def test_get_language_rules_invalid_section(srv) -> None:
    result = await _call(
        srv, "playbook_get_doc", kind="language", project="proj-a", name="java", section="bogus"
    )
    assert "must be one of" in result[0].text


async def test_get_workflow(srv) -> None:
    result = await _call(
        srv, "playbook_get_doc", kind="workflow", project="proj-a", name="bug-fix"
    )
    text = result[0].text
    assert "Reproduce" in text
    # see_also drives Next Calls via playbook_get_doc
    assert "Next Calls" in text
    assert 'kind="skill"' in text
    assert 'kind="pattern"' in text


async def test_see_also_core_kind_renders(srv) -> None:
    """`core:guardrails` used to be silently dropped by _format_call, so three
    real nexre workflows shipped with a Next Call that rendered nothing."""
    result = await _call(
        srv, "playbook_get_doc", kind="workflow", project="proj-a", name="bug-fix"
    )
    assert 'playbook_get_doc(project="proj-a", kind="guardrails")' in result[0].text


async def test_see_also_gates_alias_renders(srv) -> None:
    """Same bug, plural spelling: `gates:README` rendered nothing."""
    result = await _call(srv, "playbook_get_doc", kind="skill", project="proj-a", name="bar")
    assert 'playbook_get_doc(project="proj-a", kind="gate")' in result[0].text


async def test_get_gate_listing(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="gate", project="proj-a")
    text = result[0].text
    assert "verify-java.sh" in text
    assert "Available scripts" in text


async def test_get_gate_named(srv) -> None:
    result = await _call(
        srv, "playbook_get_doc", kind="gate", project="proj-a", name="verify-java"
    )
    text = result[0].text
    assert "verify-java.sh" in text
    assert "does not execute" in text


async def test_get_gate_named_shows_script_body(srv) -> None:
    """The description promises the script's first lines; it used to show only
    the path."""
    result = await _call(
        srv, "playbook_get_doc", kind="gate", project="proj-a", name="verify-java"
    )
    assert "echo ok" in result[0].text


async def test_get_gate_unknown_script(srv) -> None:
    result = await _call(
        srv, "playbook_get_doc", kind="gate", project="proj-a", name="verify-zzz"
    )
    assert "not found" in result[0].text.lower()


async def test_start_task_matches_workflow_via_trigger(srv) -> None:
    result = await _call(
        srv, "playbook_start_task", project="proj-a", task="please fix a bug in the route"
    )
    text = result[0].text
    assert "Guardrails" in text
    assert "Definition of Done" in text
    assert "bug-fix" in text
    assert "Next Calls" in text
    assert 'kind="skill"' in text


async def test_start_task_inlines_identity(srv) -> None:
    """playbook_start_task subsumes the one part of AGENTS.md it did not already
    cover, so there is no reason left to call playbook_get_doc(kind=agents) first."""
    result = await _call(srv, "playbook_start_task", project="proj-a", task="fix a bug")
    text = result[0].text
    assert "senior proj-a engineer" in text
    # ...but not the rest of AGENTS.md, which just restates the guardrails.
    assert "errorHandler boundaries" not in text


async def test_start_task_unknown_project(srv) -> None:
    result = await _call(srv, "playbook_start_task", project="nope", task="something")
    assert "not found" in result[0].text.lower()


async def test_start_task_missing_project_asks_which(srv) -> None:
    """`project` is schema-required; a non-enforcing client that omits it must
    still get the teaching error listing the valid projects."""
    result = await _call(srv, "playbook_start_task", task="fix a bug")
    text = result[0].text.lower()
    assert "which project" in text
    assert "proj-a" in text
    assert "proj-b" in text


async def test_get_doc_missing_project_asks_which(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="guardrails")
    text = result[0].text.lower()
    assert "which project" in text


async def test_get_pattern(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="pattern", project="proj-a", name="foo")
    assert "Pattern: Foo" in result[0].text


async def test_get_pattern_missing(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="pattern", project="proj-a", name="zzz")
    assert "not found" in result[0].text.lower()
    assert "playbook_search_docs" in result[0].text


async def test_get_skill(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="skill", project="proj-a", name="bar")
    assert "Skill: Bar" in result[0].text


async def test_get_skill_missing(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="skill", project="proj-a", name="zzz")
    assert "not found" in result[0].text.lower()


async def test_get_doc_requires_name_for_pattern(srv) -> None:
    result = await _call(srv, "playbook_get_doc", kind="pattern", project="proj-a")
    assert "name" in result[0].text.lower()


async def test_legacy_get_pattern_removed(srv) -> None:
    result = await _call(srv, "get_pattern", project="proj-a", pattern="foo")
    assert "Unknown tool" in result[0].text


async def test_pre_070_unprefixed_names_removed(srv) -> None:
    """Breaking change in 0.7.0: the unprefixed tool names are gone."""
    for old in ("start_task", "get_doc", "find_rules", "list_requirements", "start_requirement"):
        result = await _call(srv, old, project="proj-a", task="x", kind="agents", intent="x")
        assert "Unknown tool" in result[0].text, old


async def test_search_docs_search_mode(srv) -> None:
    result = await _call(srv, "playbook_search_docs", project="proj-a", query="DLQ flows")
    assert "patterns/foo.md" in result[0].text


async def test_search_docs_blank_query_falls_back_to_list(srv) -> None:
    """A whitespace-only query is a listing request, not an error."""
    result = await _call(srv, "playbook_search_docs", project="proj-a", query="   ")
    assert "patterns/foo.md" in result[0].text


async def test_search_docs_top_k_bounds_clamp(srv) -> None:
    """Bad top_k values are clamped, not crashed on."""
    r1 = await _call(srv, "playbook_search_docs", project="proj-a", query="agents", top_k=-5)
    r2 = await _call(srv, "playbook_search_docs", project="proj-a", query="agents", top_k=9999)
    assert r1[0].text  # both should produce non-empty results, no exception
    assert r2[0].text


async def test_search_rules_removed(srv) -> None:
    """Breaking change: search_rules merged into playbook_search_docs query mode."""
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
    # 5 playbook_-namespaced tools (list_projects removed in 0.7.0).
    assert len(tools) == 5
    names = {t.name for t in tools}
    assert names == {
        "playbook_start_task",
        "playbook_search_docs",
        "playbook_get_doc",
        "playbook_list_requirements",
        "playbook_start_requirement",
    }
    for t in tools:
        assert t.annotations is not None, f"{t.name} has no annotations"
        assert t.annotations.readOnlyHint is True, t.name
        assert t.annotations.openWorldHint is False, t.name


async def test_every_tool_requires_project(srv) -> None:
    """0.7.0: `project` is required on every tool - no inference surprises."""
    tools = await srv.list_tools()
    for t in tools:
        assert "project" in (t.inputSchema.get("required") or []), t.name


async def test_exactly_one_tool_claims_to_be_first(srv) -> None:
    """playbook_start_task is the coding entry point. playbook_start_requirement
    is PM-only and must not use the same entry phrasing or agents get confused."""
    directive = re.compile(r"entry point for any coding task", re.IGNORECASE)
    tools = await srv.list_tools()
    claimants = [t.name for t in tools if directive.search(t.description or "")]
    assert claimants == ["playbook_start_task"]


async def test_server_instructions_name_the_entry_point(srv) -> None:
    """The cross-tool workflow lives in server-level instructions, not in
    ALL-CAPS tool descriptions."""
    opts = srv._initialization_options()
    assert opts.instructions
    assert "playbook_start_task" in opts.instructions


async def test_get_error_conventions_removed(srv) -> None:
    """Breaking change in 0.2.0: the redundant tool is gone."""
    result = await _call(srv, "get_error_conventions", project="proj-b")
    assert "Unknown tool" in result[0].text


def test_format_call_renders_get_doc_for_all_kinds() -> None:
    """Every see_also / targets kind must render a playbook_get_doc (or
    entry-point) call; pre-0.7.0 tool aliases render as the new names."""
    from tools.docs import _format_call

    project = "nexre"
    cases = [
        ("pattern", "repository", 'kind="pattern"', 'name="repository"'),
        ("skill", "add-screen", 'kind="skill"', 'name="add-screen"'),
        ("workflow", "bug-fix", 'kind="workflow"', 'name="bug-fix"'),
        ("gate", "README", 'kind="gate"', None),
        ("gates", "verify-java", 'kind="gate"', 'name="verify-java"'),
        ("language", "kotlin", 'kind="language"', 'name="kotlin"'),
        ("language", "kotlin/testing", 'kind="language"', 'section="testing"'),
        ("architecture", "overview", 'kind="architecture"', None),
        ("architecture", "0001-foo", 'kind="architecture"', 'name="0001-foo"'),
        ("core", "guardrails", 'kind="guardrails"', None),
        ("requirement", "ST-101", 'kind="requirement"', 'name="ST-101"'),
        ("agents", "AGENTS", 'kind="agents"', None),
        ("tool", "start_task", "playbook_start_task(", None),
        ("tool", "playbook_start_task", "playbook_start_task(", None),
        ("tool", "get_guardrails", 'kind="guardrails"', None),
        ("tool", "find_rules", "playbook_search_docs(", None),
        ("tool", "playbook_search_docs", "playbook_search_docs(", None),
    ]
    for kind, name, must_contain, also in cases:
        rendered = _format_call(kind, project, name)
        assert rendered, f"{kind}:{name} rendered nothing"
        assert must_contain in rendered, f"{kind}:{name} → {rendered}"
        if also:
            assert also in rendered, f"{kind}:{name} missing {also} in {rendered}"

    # list_projects is gone: its frontmatter entry renders nothing.
    assert _format_call("tool", project, "list_projects") is None
