"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `mcp/` importable as a flat package layout.
_MCP_DIR = Path(__file__).resolve().parent.parent
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))


@pytest.fixture
def tmp_rules_root(tmp_path: Path) -> Path:
    """
    Build a small fake rules tree:

        tmp/
          proj-a/
            agents.md            (with frontmatter)
            architecture.md
            patterns/foo.md
            skills/bar.md
          proj-b/
            agents.md            (no frontmatter)
            error-conventions.md
            stray.md             (lands in 'other')
          README.md              (excluded)
          loose.md               (top-level, warned + skipped)
    """
    (tmp_path / "proj-a").mkdir()
    (tmp_path / "proj-a" / "patterns").mkdir()
    (tmp_path / "proj-a" / "skills").mkdir()
    (tmp_path / "proj-b").mkdir()

    (tmp_path / "proj-a" / "agents.md").write_text(
        "---\n"
        "title: Proj A agents\n"
        "description: Identity and behavior for proj-a.\n"
        "tags: [stack-a, rest]\n"
        "---\n"
        "# AGENTS.md — Proj A\n\n"
        "Be careful with errorHandler boundaries.\n"
    )
    (tmp_path / "proj-a" / "architecture.md").write_text(
        "# Architecture — Proj A\n\nModules: api, service, model.\n"
    )
    (tmp_path / "proj-a" / "patterns" / "foo.md").write_text(
        "# Pattern: Foo — Proj A\n\nUse Foo when handling DLQ flows.\n"
    )
    (tmp_path / "proj-a" / "skills" / "bar.md").write_text(
        "# Skill: Bar — when adding a new connector\n\nSteps: 1. ... 2. ... 3. ...\n"
    )
    (tmp_path / "proj-b" / "agents.md").write_text("# AGENTS.md — Proj B\n\nDifferent stack.\n")
    (tmp_path / "proj-b" / "error-conventions.md").write_text(
        "# Error Conventions — Proj B\n\nUse 502 for upstream gateway failures.\n"
    )
    (tmp_path / "proj-b" / "stray.md").write_text("# Stray\n\nThis is not a recognized doc type.\n")
    (tmp_path / "README.md").write_text("# repo readme — should be excluded\n")
    (tmp_path / "loose.md").write_text("# loose — should be skipped with warning\n")
    return tmp_path
