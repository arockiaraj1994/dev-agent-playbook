#!/usr/bin/env python3
"""
validate-rules.py — Pre-commit / CI gate for rule docs.

Checks:
  1. Each project directory contains agents.md (required).
  2. Optional YAML frontmatter parses cleanly (uses mcp.loader).
  3. Doc type inferred from path is not 'other' (warns; doesn't fail).
  4. Relative markdown links resolve to existing files.

Exits non-zero on errors; warnings do not fail the run.

Usage:
    python scripts/validate-rules.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = REPO_ROOT / "mcp"

# Reuse the loader so this script always agrees with what the server sees.
sys.path.insert(0, str(MCP_DIR))
from loader import _parse_docs, _parse_frontmatter  # noqa: E402

EXCLUDED_DIRS = {"mcp", ".git", ".github", "scripts", ".venv"}

# Markdown link: [text](target)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _project_dirs(repo_root: Path) -> list[Path]:
    return [
        p for p in sorted(repo_root.iterdir())
        if p.is_dir() and not p.name.startswith(".") and p.name not in EXCLUDED_DIRS
    ]


def _check_required_agents_md(projects: list[Path]) -> list[str]:
    errors: list[str] = []
    for project in projects:
        agents = project / "agents.md"
        if not agents.is_file():
            errors.append(f"missing required file: {project.name}/agents.md")
    return errors


def _check_frontmatter(repo_root: Path) -> list[str]:
    """
    Parse every rule doc the loader would index. _parse_docs reads each file
    and runs _parse_frontmatter; if there's a hard parse error, it would have
    already raised — we re-run frontmatter parsing here with stricter checks.
    """
    errors: list[str] = []
    for md in repo_root.rglob("*.md"):
        rel = md.relative_to(repo_root)
        if rel.parts[0] in EXCLUDED_DIRS:
            continue
        if len(rel.parts) < 2:
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(f"{rel}: cannot read ({e})")
            continue
        if content.startswith("---"):
            metadata, _ = _parse_frontmatter(content)
            # Re-find the boundary; if missing, _parse_frontmatter returns ({}, content)
            # but we want to flag the malformed case explicitly.
            if not metadata and "---" not in content[3:]:
                errors.append(f"{rel}: starts with '---' but no closing '---' boundary")
    return errors


def _check_links(repo_root: Path) -> list[str]:
    """Validate relative markdown links. External (http(s)://) and anchors are skipped."""
    errors: list[str] = []
    for md in repo_root.rglob("*.md"):
        rel = md.relative_to(repo_root)
        if rel.parts[0] in EXCLUDED_DIRS:
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except OSError:
            continue
        for _, target in LINK_RE.findall(content):
            if (
                target.startswith(("http://", "https://", "mailto:", "#"))
                or target.startswith("<")
            ):
                continue
            # strip anchor / query
            path_part = target.split("#", 1)[0].split("?", 1)[0]
            if not path_part:
                continue
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                errors.append(f"{rel}: broken link -> {target}")
    return errors


def main() -> int:
    print(f"Validating rules under {REPO_ROOT}")
    projects = _project_dirs(REPO_ROOT)
    if not projects:
        print("ERROR: no project directories found.", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors += _check_required_agents_md(projects)
    errors += _check_frontmatter(REPO_ROOT)
    errors += _check_links(REPO_ROOT)

    # Use _parse_docs for an end-to-end sanity check (also surfaces 'other' warnings).
    docs = _parse_docs(REPO_ROOT)
    print(f"  Loaded {len(docs)} rule docs across {len(projects)} project(s).")

    if errors:
        print(f"\nFAILED: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
