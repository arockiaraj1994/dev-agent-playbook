"""
corpus.py - CorpusSpec for standards/ and requirements/ roots.

Two env vars make a future repo split a config change, not a rewrite:
  MCP_STANDARDS_ROOT - default <repo>/standards
  MCP_REQUIREMENTS_ROOT - default <repo>/requirements
  MCP_REQUIREMENTS_TTL - seconds (default 300)
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent
_REPO = _MCP_DIR.parent

_PRD_FOLDER_RE = re.compile(r"^(PRD-\d+)(?:-.*)?$")
_STORY_FILE_RE = re.compile(r"^(ST-\d+)(?:-.*)?$")


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return default


def infer_standards_type(relative_path: str) -> tuple[str, str]:
    """Infer (doc_type, name) for a path inside a standards project directory."""
    parts = Path(relative_path).parts
    stem = Path(relative_path).stem

    if relative_path == "AGENTS.md":
        return "agents", "agents"
    if relative_path == "INDEX.md":
        return "index", "index"

    if len(parts) < 2:
        return "other", stem

    head = parts[0]

    if head == "core":
        if relative_path == "core/guardrails.md":
            return "guardrails", "guardrails"
        if relative_path == "core/definition-of-done.md":
            return "definition-of-done", "definition-of-done"
        if relative_path == "core/glossary.md":
            return "glossary", "glossary"
        return "other", stem

    if head == "architecture":
        if relative_path == "architecture/overview.md":
            return "architecture", "overview"
        if len(parts) >= 3 and parts[1] == "decisions":
            return "architecture-decision", stem
        return "other", stem

    if head == "languages":
        if len(parts) == 3:
            lang = parts[1]
            return "language-rules", f"{lang}/{stem}"
        return "other", stem

    if head == "patterns":
        return "pattern", stem

    if head == "skills":
        return "skill", stem

    if head == "workflows":
        return "workflow", stem

    if head == "gates":
        if relative_path == "gates/README.md":
            return "gate", "gate"
        return "other", stem

    return "other", stem


def infer_requirements_type(relative_path: str) -> tuple[str, str]:
    """Infer (doc_type, provisional_name) for a path inside a requirements project.

    Provisional name is the folder/file prefix (PRD-003 / ST-114). Callers
    should prefer frontmatter `id:` when present - the loader overrides
    `name` from metadata after parsing.
    """
    parts = Path(relative_path).parts
    stem = Path(relative_path).stem

    if relative_path == "AGENTS.md":
        return "req-agents", "agents"
    if relative_path == "INDEX.md":
        return "index", "index"

    if len(parts) >= 2 and parts[0] == "workflows":
        return "req-workflow", stem

    # PRD-003-offline-sync/prd.md
    if len(parts) == 2 and parts[1] == "prd.md":
        m = _PRD_FOLDER_RE.match(parts[0])
        if m:
            return "prd", m.group(1)
        return "other", stem

    # PRD-003-offline-sync/stories/ST-114-queue-writes.md
    if len(parts) == 3 and parts[1] == "stories":
        folder_m = _PRD_FOLDER_RE.match(parts[0])
        story_m = _STORY_FILE_RE.match(stem)
        if folder_m and story_m:
            return "story", story_m.group(1)
        return "other", stem

    return "other", stem


KNOWN_STANDARDS_DOC_TYPES = (
    "agents",
    "index",
    "guardrails",
    "definition-of-done",
    "glossary",
    "architecture",
    "architecture-decision",
    "language-rules",
    "pattern",
    "skill",
    "workflow",
    "gate",
)

KNOWN_REQUIREMENTS_DOC_TYPES = (
    "req-agents",
    "index",
    "req-workflow",
    "prd",
    "story",
)

KNOWN_DOC_TYPES = tuple(dict.fromkeys([*KNOWN_STANDARDS_DOC_TYPES, *KNOWN_REQUIREMENTS_DOC_TYPES]))


@dataclass(frozen=True)
class CorpusSpec:
    name: str  # "standards" | "requirements"
    root: Path
    cache_policy: str  # "boot" | "ttl"
    infer: Callable[[str], tuple[str, str]]
    ttl_seconds: int = 0
    excluded_files: frozenset[str] = field(default_factory=lambda: frozenset({"README.md"}))


def standards_spec() -> CorpusSpec:
    return CorpusSpec(
        name="standards",
        root=_env_path("MCP_STANDARDS_ROOT", _REPO / "standards"),
        cache_policy="boot",
        infer=infer_standards_type,
    )


def requirements_spec() -> CorpusSpec:
    ttl_raw = os.getenv("MCP_REQUIREMENTS_TTL", "300").strip()
    try:
        ttl = int(ttl_raw)
    except ValueError:
        ttl = 300
    return CorpusSpec(
        name="requirements",
        root=_env_path("MCP_REQUIREMENTS_ROOT", _REPO / "requirements"),
        cache_policy="ttl",
        ttl_seconds=max(ttl, 0),
        infer=infer_requirements_type,
    )


# Module-level defaults resolved at import (env can still override via factory).
STANDARDS = standards_spec()
REQUIREMENTS = requirements_spec()
