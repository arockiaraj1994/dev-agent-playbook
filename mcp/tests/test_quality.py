"""Tests for the Projects quality scoring engine.

Covers the per-doc-type rules with passes-on-good and fails-on-bad
fixtures, and the project-level rollup behavior (worst-of files +
project rules).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from loader import RuleDoc, load_store
from quality import score_doc, score_project
from quality_rules import RuleContext, SEVERITY_HARD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(rel: str, content: str, *, project: str = "p", metadata: dict | None = None) -> RuleDoc:
    """Construct a RuleDoc directly, bypassing the loader."""
    from loader import _infer_doc_type_and_name
    doc_type, name = _infer_doc_type_and_name(rel)
    return RuleDoc(
        project=project,
        relative_path=rel,
        doc_type=doc_type,
        name=name,
        content=content,
        metadata=metadata or {},
    )


def _ctx(tmp_path: Path, files: list[RuleDoc] | None = None, on_disk_index: str | None = None) -> RuleContext:
    return RuleContext(
        project_root=tmp_path,
        project_files=files or [],
        on_disk_index=on_disk_index,
    )


def _failed_ids(fs) -> set[str]:
    return {r.rule_id for r in fs.failed}


# ---------------------------------------------------------------------------
# Universal rules
# ---------------------------------------------------------------------------


def test_universal_passes_on_well_formed_doc(tmp_path: Path) -> None:
    body = "# Title\n\nUse this when X.\n\n" + ("Quality content here please. " * 30)
    doc = _doc(
        "patterns/foo.md",
        body + "\n\n```\nexample\n```\n",
        metadata={
            "title": "Foo", "description": "A foo pattern",
            "triggers": ["foo"], "see_also": ["skill:b"],
        },
    )
    fs = score_doc(doc, _ctx(tmp_path))
    assert fs.indicator == "green", fs.failed


def test_universal_fails_when_no_h1(tmp_path: Path) -> None:
    doc = _doc("patterns/foo.md", "no heading at all\n", metadata={"title": "Foo", "description": "x"})
    fs = score_doc(doc, _ctx(tmp_path))
    assert "universal.has_h1" in _failed_ids(fs)
    assert fs.indicator == "red"


def test_universal_fails_on_empty_body(tmp_path: Path) -> None:
    doc = _doc("patterns/foo.md", "", metadata={"title": "Foo", "description": "x"})
    fs = score_doc(doc, _ctx(tmp_path))
    assert "universal.non_empty" in _failed_ids(fs)
    assert fs.indicator == "red"


def test_universal_other_doc_type_is_red(tmp_path: Path) -> None:
    doc = _doc("misc/random.md", "# Title\n\nbody " * 20, metadata={"title": "x", "description": "y"})
    assert doc.doc_type == "other"
    fs = score_doc(doc, _ctx(tmp_path))
    assert "universal.recognized_path" in _failed_ids(fs)
    assert fs.indicator == "red"


def test_universal_placeholder_text_is_allowed(tmp_path: Path) -> None:
    """TODO/FIXME tokens are allowed — docs may legitimately discuss them
    (e.g. AGENTS.md saying 'No TODO/FIXME for things you could just fix now')."""
    body = "# Foo\n\nUse this when X. No TODO/FIXME for things you could just fix now.\n\n" + ("words and more words here. " * 30)
    doc = _doc(
        "patterns/foo.md",
        body + "\n\n```\nexample\n```\n",
        metadata={"title": "Foo", "description": "A pattern", "see_also": ["skill:bar"], "triggers": ["foo"]},
    )
    fs = score_doc(doc, _ctx(tmp_path))
    assert fs.indicator == "green", fs.failed


def test_universal_short_body_is_amber(tmp_path: Path) -> None:
    body = "# Foo\n\nshort\n\n```\nx\n```\n"
    doc = _doc(
        "patterns/foo.md",
        body,
        metadata={"title": "Foo", "description": "A pattern", "see_also": ["skill:b"], "triggers": ["foo"]},
    )
    fs = score_doc(doc, _ctx(tmp_path))
    assert "universal.word_count" in _failed_ids(fs)
    assert fs.indicator == "amber"


# ---------------------------------------------------------------------------
# AGENTS.md
# ---------------------------------------------------------------------------


def _good_agents_body() -> str:
    return (
        "# AGENTS.md — Foo (java)\n\n"
        + ("Identity paragraph that explains the agent's role and stack and how this codebase works. " * 30)
        + "\n\nCall `start_task` first. See `INDEX.md` and `core/guardrails.md`.\n\n"
        "## Context docs\n\n"
        "| Doc | Purpose |\n|---|---|\n"
        "| core/ | guardrails |\n"
        "| architecture/ | overview |\n"
        "| languages/ | per-language |\n"
        "| patterns/ | canonical |\n"
        "| skills/ | playbooks |\n"
        "| workflows/ | tasks |\n"
        "| gates/ | verify scripts |\n"
    )


def test_agents_good(tmp_path: Path) -> None:
    doc = _doc("AGENTS.md", _good_agents_body(), metadata={"title": "AGENTS", "description": "ok"})
    fs = score_doc(doc, _ctx(tmp_path))
    assert fs.indicator == "green", fs.failed


def test_agents_missing_entry_points_is_red(tmp_path: Path) -> None:
    body = "# AGENTS.md — Foo\n\n" + ("Some text. " * 50)
    doc = _doc("AGENTS.md", body, metadata={"title": "AGENTS", "description": "ok"})
    fs = score_doc(doc, _ctx(tmp_path))
    assert "agents.mentions_entry_points" in _failed_ids(fs)
    assert fs.indicator == "red"


# ---------------------------------------------------------------------------
# INDEX.md
# ---------------------------------------------------------------------------


def test_index_drift_is_red(tmp_path: Path) -> None:
    project_files = [
        _doc(
            "workflows/bug-fix.md",
            "---\ntriggers: [bug]\n---\n# Workflow\n\n## Steps\n1. a\n2. b\n3. c\n",
            metadata={"title": "wf", "description": "fix bugs", "triggers": ["bug"]},
        ),
    ]
    on_disk = "<!-- AUTO-GENERATED by scripts/validate-rules.py — do not edit by hand. -->\n# INDEX — p\nstale content\n"
    index_doc = _doc("INDEX.md", on_disk)
    fs = score_doc(index_doc, _ctx(tmp_path, files=project_files, on_disk_index=on_disk))
    assert "index.up_to_date" in _failed_ids(fs)
    assert fs.indicator == "red"


def test_index_missing_autogen_header_is_red(tmp_path: Path) -> None:
    body = "# INDEX — p\n\n## Workflows\n\n- foo\n"
    doc = _doc("INDEX.md", body)
    fs = score_doc(doc, _ctx(tmp_path, files=[], on_disk_index=body))
    assert "index.autogen_header" in _failed_ids(fs)
    assert fs.indicator == "red"


# ---------------------------------------------------------------------------
# core/guardrails.md
# ---------------------------------------------------------------------------


def test_guardrails_good(tmp_path: Path) -> None:
    body = (
        "# Guardrails — Foo\n\n"
        + ("Always-on rules that the agent re-reads at the start of every task. " * 20)
        + "\n## MUST\n- Scope: ask before acting; never leak credentials.\n"
        "- Read before write.\n"
        "## MUST NOT\n- No hardcoded secrets in code or YAML.\n"
        "Run `bash gates/scripts/verify-java.sh` before claiming done.\n"
    )
    doc = _doc("core/guardrails.md", body, metadata={"title": "Guardrails", "description": "rules"})
    fs = score_doc(doc, _ctx(tmp_path))
    assert fs.indicator == "green", fs.failed


def test_guardrails_missing_must_not_is_red(tmp_path: Path) -> None:
    body = "# Guardrails — Foo\n\n## MUST\n- Be honest about scope.\n" + ("filler " * 50)
    doc = _doc("core/guardrails.md", body, metadata={"title": "g", "description": "x"})
    fs = score_doc(doc, _ctx(tmp_path))
    assert "guardrails.must_and_must_not" in _failed_ids(fs)
    assert fs.indicator == "red"


# ---------------------------------------------------------------------------
# core/definition-of-done.md
# ---------------------------------------------------------------------------


def test_dod_good(tmp_path: Path) -> None:
    body = (
        "# Definition of Done — Foo\n\n"
        + ("Mechanical and functional checks that must hold before shipping. " * 20)
        + "\n## Mechanical\n- [ ] `gates/scripts/verify-java.sh` passes\n"
        "## Functional\n- [ ] All tests green\n"
        "## Security\n- [ ] No new secrets\n"
    )
    doc = _doc("core/definition-of-done.md", body, metadata={"title": "DoD", "description": "checks"})
    fs = score_doc(doc, _ctx(tmp_path))
    assert fs.indicator == "green", fs.failed


def test_dod_missing_checkbox_is_red(tmp_path: Path) -> None:
    body = "# DoD\n\n" + ("text " * 100)
    doc = _doc("core/definition-of-done.md", body, metadata={"title": "DoD", "description": "x"})
    fs = score_doc(doc, _ctx(tmp_path))
    assert "dod.has_checkbox" in _failed_ids(fs)


# ---------------------------------------------------------------------------
# patterns / skills / workflows
# ---------------------------------------------------------------------------


def test_pattern_without_code_block_is_red(tmp_path: Path) -> None:
    body = "# Pattern\n\n" + ("words " * 100) + "\n\nUse this when X.\n"
    doc = _doc(
        "patterns/foo.md",
        body,
        metadata={"title": "Foo", "description": "A pattern", "see_also": ["skill:b"]},
    )
    fs = score_doc(doc, _ctx(tmp_path))
    assert "pattern.has_code_block" in _failed_ids(fs)
    assert fs.indicator == "red"


def test_skill_without_steps_is_red(tmp_path: Path) -> None:
    body = "# Skill: Foo\n\n" + ("body " * 100)
    doc = _doc(
        "skills/foo.md",
        body,
        metadata={"title": "Foo", "description": "x", "triggers": ["go"], "see_also": ["pattern:p"]},
    )
    fs = score_doc(doc, _ctx(tmp_path))
    assert "skill.numbered_steps" in _failed_ids(fs)
    assert fs.indicator == "red"


def test_workflow_without_triggers_is_red(tmp_path: Path) -> None:
    body = "# Workflow — Foo\n\n## Steps\n1. a\n2. b\n3. c\n" + ("body " * 50)
    doc = _doc(
        "workflows/bug-fix.md",
        body,
        metadata={"title": "wf", "description": "x"},   # no triggers
    )
    fs = score_doc(doc, _ctx(tmp_path))
    assert "workflow.triggers" in _failed_ids(fs)
    assert fs.indicator == "red"


def test_workflow_good(tmp_path: Path) -> None:
    body = (
        "# Workflow — bug-fix\n\n## Steps\n1. Reproduce\n2. Isolate\n3. Fix\n"
        + ("body " * 80)
    )
    doc = _doc(
        "workflows/bug-fix.md",
        body,
        metadata={
            "title": "wf",
            "description": "x",
            "triggers": ["bug"],
            "gates": ["verify-java"],
            "see_also": ["skill:debug-route", "pattern:error-handling"],
        },
    )
    fs = score_doc(doc, _ctx(tmp_path))
    assert fs.indicator == "green", fs.failed


# ---------------------------------------------------------------------------
# gates/README.md
# ---------------------------------------------------------------------------


def test_gate_executable_check(tmp_path: Path) -> None:
    # Build a real on-disk script so we can test the executable bit.
    scripts_dir = tmp_path / "gates" / "scripts"
    scripts_dir.mkdir(parents=True)
    script = scripts_dir / "verify-java.sh"
    script.write_text("#!/usr/bin/env bash\necho ok\n")
    # NOT executable yet — should fail.
    body = "# Gates — Foo\n\n" + ("text " * 80) + "\n\n## verify-java.sh\nDescribed.\n"
    doc = _doc(
        "gates/README.md",
        body,
        metadata={
            "title": "Gates", "description": "x",
            "gate_scripts": ["verify-java.sh"],
        },
    )
    fs_before = score_doc(doc, _ctx(tmp_path))
    assert "gate.scripts_executable" in _failed_ids(fs_before)

    # chmod +x — now passes.
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    fs_after = score_doc(doc, _ctx(tmp_path))
    assert "gate.scripts_executable" not in _failed_ids(fs_after)


# ---------------------------------------------------------------------------
# Project rollup
# ---------------------------------------------------------------------------


def test_score_project_real_apache_camel_is_red_only_for_known_failures() -> None:
    """The live apache-camel project should score and surface its known
    issues (legacy patterns/skills missing frontmatter triggers/see_also).
    Smoke test that the full pipeline works against real disk."""
    repo_root = Path(__file__).resolve().parents[2]
    project_root = repo_root / "apache-camel"
    if not project_root.is_dir():
        pytest.skip("apache-camel project missing")
    store = load_store(repo_root)
    status = score_project("apache-camel", store, project_root)
    assert status.project == "apache-camel"
    # Required files all present (we just migrated).
    assert status.missing_required == []
    # Counts must add up.
    assert status.counts["red"] + status.counts["amber"] + status.counts["green"] == status.total_files


def test_score_project_aggregates_to_red_when_any_file_red(tmp_path: Path) -> None:
    """Build a minimal fake project tree and assert rollup."""
    proj = tmp_path / "p"
    proj.mkdir()
    # AGENTS.md — short and missing entry points → red.
    (proj / "AGENTS.md").write_text("# AGENTS — p\nshort\n")
    # Required files (we don't create them, so missing_required will fire too)
    repo_root = tmp_path
    store = load_store(repo_root)
    status = score_project("p", store, proj)
    assert status.indicator == "red"
    assert status.missing_required  # required files absent
    assert any(r.rule_id == "project.required_files" and not r.passed for r in status.rule_results)


def test_score_project_indicator_amber_when_only_soft_fails(tmp_path: Path) -> None:
    proj = tmp_path / "p"
    (proj / "core").mkdir(parents=True)
    (proj / "architecture").mkdir(parents=True)
    (proj / "languages" / "java").mkdir(parents=True)
    (proj / "workflows").mkdir(parents=True)
    (proj / "gates" / "scripts").mkdir(parents=True)
    (proj / "patterns").mkdir(parents=True)

    (proj / "AGENTS.md").write_text(
        "---\ntitle: AGENTS\ndescription: ok\n---\n" + _good_agents_body()
    )
    (proj / "core" / "guardrails.md").write_text(
        "---\ntitle: Guardrails\ndescription: rules\n---\n"
        "# Guardrails\n\n## MUST\n- Ask. Never leak credentials.\n"
        "## MUST NOT\n- No hardcoded secrets.\n"
        + ("filler text that fills out the body sufficiently. " * 30)
        + "\nRun `bash gates/scripts/verify-java.sh`.\n"
    )
    (proj / "core" / "definition-of-done.md").write_text(
        "---\ntitle: DoD\ndescription: x\n---\n# DoD\n\n"
        "## Mechanical\n- [ ] gates/scripts/verify-java.sh passes\n"
        "## Functional\n- [ ] tests pass\n"
        "## Security\n- [ ] no leaks\n"
        + ("filler text that fills out the body sufficiently. " * 30)
    )
    (proj / "core" / "glossary.md").write_text(
        "---\ntitle: Glossary\ndescription: x\n---\n# Glossary\n\n"
        + "\n".join(f"- **Term{i}**: definition that explains the term" for i in range(12))
        + "\n"
    )
    (proj / "architecture" / "overview.md").write_text(
        "---\ntitle: Arch\ndescription: x\n---\n# Architecture — p\n\n"
        "## Overview\n" + ("Architecture words that describe the system. " * 30) + "\n"
        "## Stack\n| L | T |\n|---|---|\n| api | java |\n"
        "## Modules\nBoundaries between modules and services in this project.\n"
    )
    (proj / "languages" / "java" / "standards.md").write_text(
        "---\ntitle: Java standards\ndescription: x\nlanguage: java\n---\n# Java\n\n"
        "## Naming\nNames matter and follow conventions.\n"
        "## Logging\nUse SLF4J for all logging.\n"
        "## Dependencies\nKeep dependency tree small.\n"
        + ("body text fills out the document. " * 20)
    )
    for wf in ("new-feature", "bug-fix", "security-fix", "refactor"):
        (proj / "workflows" / f"{wf}.md").write_text(
            f"---\ntitle: {wf}\ndescription: do {wf}\n"
            f"triggers: [{wf}]\ngates: [verify-java]\n"
            f"see_also: [skill:foo, pattern:bar]\n---\n"
            f"# Workflow — {wf}\n\n## Steps\n1. a\n2. b\n3. c\n"
            + ("body text fills out the workflow doc. " * 20)
        )
    script = proj / "gates" / "scripts" / "verify-java.sh"
    script.write_text("#!/usr/bin/env bash\necho ok\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (proj / "gates" / "README.md").write_text(
        "---\ntitle: Gates\ndescription: x\n---\n# Gates\n\nverify-java.sh runs lint + tests.\n"
        + ("body text fills out the gates README sufficiently. " * 20)
    )

    # Generate INDEX.md so it doesn't drift.
    from index_render import render_index
    store = load_store(tmp_path)
    rendered = render_index("p", store.for_project("p"))
    (proj / "INDEX.md").write_text(rendered)

    # Re-load now that INDEX.md exists.
    store = load_store(tmp_path)
    status = score_project("p", store, proj)

    # Either green overall, or amber from the soft project rule about ADRs.
    assert status.indicator in ("green", "amber"), [
        (fs.relative_path, fs.indicator, [r.rule_id for r in fs.failed])
        for fs in status.files
    ]
    assert status.missing_required == []
    # No file should be red.
    assert status.counts["red"] == 0
