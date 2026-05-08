#!/usr/bin/env python3
"""
validate-rules.py — Pre-commit / CI gate for rule docs.

Responsibilities:
  1. Validate the per-project layout under <repo>/<project>/:
       - AGENTS.md present
       - core/{guardrails,definition-of-done,glossary}.md present
       - architecture/overview.md present
       - At least one languages/<lang>/standards.md
       - All workflows present (new-feature, bug-fix, security-fix, refactor)
       - gates/README.md present, gates/scripts/*.sh executable
  2. Optional YAML frontmatter parses cleanly.
  3. Doc type inferred from path is never `other`.
  4. Relative markdown links resolve.
  5. Auto-generate (or check) <project>/INDEX.md from frontmatter.

Modes:
    python scripts/validate-rules.py             # validate
    python scripts/validate-rules.py --regen-index   # rewrite INDEX.md
    python scripts/validate-rules.py --check     # validate + check INDEX.md is up to date

Exits non-zero on any error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


# ANSI helpers (disabled when not a TTY)
def _c(code: str, text: str) -> str:
    if not sys.stderr.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _red(t: str) -> str: return _c("31", t)
def _yellow(t: str) -> str: return _c("33", t)
def _bold(t: str) -> str: return _c("1", t)
def _dim(t: str) -> str: return _c("2", t)

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = REPO_ROOT / "mcp"

# Reuse the loader so this script always agrees with what the server sees.
sys.path.insert(0, str(MCP_DIR))
from loader import (  # noqa: E402
    RuleDoc,
    _parse_docs,
    _parse_frontmatter,
)
from index_render import render_index  # noqa: E402

EXCLUDED_DIRS = {"mcp", "docs", ".git", ".github", "scripts", ".venv"}

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

REQUIRED_FILES = (
    "AGENTS.md",
    "core/guardrails.md",
    "core/definition-of-done.md",
    "core/glossary.md",
    "architecture/overview.md",
    "gates/README.md",
)
REQUIRED_WORKFLOWS = ("new-feature", "bug-fix", "security-fix", "refactor")


# ---------------------------------------------------------------------------
# Project discovery
# ---------------------------------------------------------------------------


def _project_dirs(repo_root: Path) -> list[Path]:
    return [
        p
        for p in sorted(repo_root.iterdir())
        if p.is_dir() and not p.name.startswith(".") and p.name not in EXCLUDED_DIRS
    ]


# ---------------------------------------------------------------------------
# Structure checks
# ---------------------------------------------------------------------------


_FIX_HINTS: dict[str, str] = {
    "missing required file": "create the file (see playbook docs for required content)",
    "expected at least one languages": "add languages/<lang>/standards.md for each stack",
    "missing workflows": "add a workflow doc under workflows/<name>.md",
    "not executable": "run: chmod +x <file>",
    "broken link": "update the link target so it points to an existing file",
    "does not match the expected layout": "rename or move the file to match the playbook layout",
    "starts with '---' but no closing": "add a closing '---' line after the YAML frontmatter",
    "out of date": "run: python scripts/validate-rules.py --regen-index",
}


def _hint(msg: str) -> str:
    for key, hint in _FIX_HINTS.items():
        if key in msg:
            return hint
    return ""


# (project, category, message) tuples — richer than bare strings
_Error = tuple[str, str, str]   # (project, category, detail)


def _check_required_files(projects: list[Path]) -> list[_Error]:
    errors: list[_Error] = []
    for project in projects:
        for rel in REQUIRED_FILES:
            if not (project / rel).is_file():
                errors.append((project.name, "required files", f"missing required file {rel}"))
        langs_dir = project / "languages"
        has_standards = False
        if langs_dir.is_dir():
            for lang_dir in langs_dir.iterdir():
                if (lang_dir / "standards.md").is_file():
                    has_standards = True
                    break
        if not has_standards:
            errors.append((
                project.name, "required files",
                "expected at least one languages/<lang>/standards.md",
            ))
        for wf in REQUIRED_WORKFLOWS:
            if not (project / "workflows" / f"{wf}.md").is_file():
                errors.append((project.name, "workflows", f"missing workflows/{wf}.md"))
        scripts_dir = project / "gates" / "scripts"
        if scripts_dir.is_dir():
            for s in scripts_dir.iterdir():
                if s.is_file() and s.suffix == ".sh" and not os.access(s, os.X_OK):
                    errors.append((
                        project.name, "gate scripts",
                        f"gates/scripts/{s.name} is not executable (chmod +x)",
                    ))
    return errors


def _check_frontmatter(repo_root: Path) -> list[_Error]:
    errors: list[_Error] = []
    for md in repo_root.rglob("*.md"):
        rel = md.relative_to(repo_root)
        if rel.parts[0] in EXCLUDED_DIRS:
            continue
        if len(rel.parts) < 2:
            continue
        project = rel.parts[0]
        try:
            content = md.read_text(encoding="utf-8")
        except OSError as e:
            errors.append((project, "frontmatter", f"{rel}: cannot read ({e})"))
            continue
        if content.startswith("---"):
            metadata, _ = _parse_frontmatter(content)
            if not metadata and "---" not in content[3:]:
                errors.append((
                    project, "frontmatter",
                    f"{rel}: starts with '---' but no closing '---' boundary",
                ))
    return errors


def _check_links(repo_root: Path) -> list[_Error]:
    errors: list[_Error] = []
    for md in repo_root.rglob("*.md"):
        rel = md.relative_to(repo_root)
        if rel.parts[0] in EXCLUDED_DIRS:
            continue
        project = rel.parts[0]
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
            path_part = target.split("#", 1)[0].split("?", 1)[0]
            if not path_part:
                continue
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                errors.append((project, "broken links", f"{rel}: broken link -> {target}"))
    return errors


def _check_no_other_doc_types(docs: list[RuleDoc]) -> list[_Error]:
    return [
        (d.project, "layout", f"{d.project}/{d.relative_path}: does not match the expected layout")
        for d in docs
        if d.doc_type == "other"
    ]


# ---------------------------------------------------------------------------
# INDEX.md generator (delegates to mcp/index_render.py)
# ---------------------------------------------------------------------------


def _regen_index(
    projects: list[Path], all_docs: list[RuleDoc], *, check_only: bool = False
) -> list[_Error]:
    """Write INDEX.md (or, in check mode, return diff errors)."""
    errors: list[_Error] = []
    by_project: dict[str, list[RuleDoc]] = {}
    for d in all_docs:
        if d.doc_type == "other":
            continue
        if d.relative_path == "INDEX.md":
            continue
        by_project.setdefault(d.project, []).append(d)

    for p in projects:
        target = p / "INDEX.md"
        rendered = render_index(p.name, by_project.get(p.name, []))
        if check_only:
            existing = target.read_text(encoding="utf-8") if target.is_file() else ""
            if existing != rendered:
                errors.append((
                    p.name, "index",
                    f"{p.name}/INDEX.md is out of date — run "
                    "`python scripts/validate-rules.py --regen-index`.",
                ))
        else:
            target.write_text(rendered, encoding="utf-8")
    return errors


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--regen-index",
        action="store_true",
        help="Regenerate <project>/INDEX.md files (writes to disk).",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="Validate AND fail if any INDEX.md is out of date.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    print(f"Validating rules under {REPO_ROOT}")
    projects = _project_dirs(REPO_ROOT)
    if not projects:
        print("ERROR: no project directories found.", file=sys.stderr)
        return 1

    docs = _parse_docs(REPO_ROOT)
    print(f"  Loaded {len(docs)} rule docs across {len(projects)} project(s).")

    if args.regen_index:
        _regen_index(projects, docs, check_only=False)
        print(f"  Regenerated INDEX.md for {len(projects)} project(s).")
        return 0

    errors: list[str] = []
    errors += _check_required_files(projects)
    errors += _check_frontmatter(REPO_ROOT)
    errors += _check_links(REPO_ROOT)
    errors += _check_no_other_doc_types(docs)

    if args.check:
        errors += _regen_index(projects, docs, check_only=True)

    if errors:
        _print_errors(errors)
        return 1
    print("OK")
    return 0


def _print_errors(errors: list[_Error]) -> None:
    total = len(errors)
    print(
        f"\n{_bold(_red('FAILED:'))} {_bold(str(total))} error(s) across "
        f"{len({e[0] for e in errors})} project(s):\n",
        file=sys.stderr,
    )

    by_project: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for project, category, msg in errors:
        by_project[project][category].append(msg)

    for project, categories in sorted(by_project.items()):
        proj_count = sum(len(v) for v in categories.values())
        print(
            f"  {_bold(_yellow(project))}  "
            f"{_dim(f'({proj_count} error(s))')}",
            file=sys.stderr,
        )
        for category, msgs in sorted(categories.items()):
            print(f"    {_bold(category)}", file=sys.stderr)
            for msg in msgs:
                hint = _hint(msg)
                print(f"      {_red('✗')} {msg}", file=sys.stderr)
                if hint:
                    print(f"        {_dim('→ ' + hint)}", file=sys.stderr)
        print(file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
