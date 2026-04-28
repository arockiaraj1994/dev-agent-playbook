"""
loader.py — Loads all markdown rule docs from disk into memory.

Optionally parses YAML frontmatter (a small dependency-free subset: scalar
strings, inline list of strings) when present at the top of a doc.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MCP_DIR = Path(__file__).resolve().parent
_DEFAULT_RULES_ROOT = _MCP_DIR.parent

# Files / dirs that are excluded from the in-memory store.
# Top-level meta files (README.md, CONTRIBUTING.md, TEMPLATE.md, CHANGELOG.md)
# are not project rules — exclude them by name.
_EXCLUDED_PREFIXES = ("mcp/", ".git/", ".github/", "scripts/")
_EXCLUDED_TOP_LEVEL_FILES = {
    "README.md",
    "CONTRIBUTING.md",
    "TEMPLATE.md",
    "CHANGELOG.md",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RuleDoc:
    project: str  # e.g. "integration-manager"
    relative_path: str  # e.g. "patterns/keycloak-oidc.md"
    doc_type: str  # agents | architecture | error-conventions | anti-patterns | glossary | pattern | skill | other
    name: str  # e.g. "keycloak-oidc"
    content: str  # body without frontmatter
    metadata: dict = field(default_factory=dict)  # parsed frontmatter (may be empty)


@dataclass
class RulesStore:
    docs: list[RuleDoc] = field(default_factory=list)

    def projects(self) -> list[str]:
        return sorted({d.project for d in self.docs})

    def get(self, project: str, relative_path: str) -> RuleDoc | None:
        for doc in self.docs:
            if doc.project == project and doc.relative_path == relative_path:
                return doc
        return None

    def for_project(self, project: str) -> list[RuleDoc]:
        return [d for d in self.docs if d.project == project]

    def of_type(self, project: str, doc_type: str) -> list[RuleDoc]:
        return [d for d in self.docs if d.project == project and d.doc_type == doc_type]

    def all_docs(self) -> list[RuleDoc]:
        return self.docs


# ---------------------------------------------------------------------------
# Frontmatter (small, dependency-free subset)
# ---------------------------------------------------------------------------

_FRONTMATTER_BOUNDARY = re.compile(r"^---\s*$", re.MULTILINE)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_inline_list(raw: str) -> list[str]:
    """Parse `[a, b, "c d"]` into ["a", "b", "c d"]. Bare strings allowed."""
    inner = raw.strip()[1:-1]  # drop [ ]
    if not inner.strip():
        return []
    items: list[str] = []
    # naive split on commas not inside quotes
    buf: list[str] = []
    in_quote: str | None = None
    for ch in inner:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
            buf.append(ch)
        elif ch == ",":
            items.append(_strip_quotes("".join(buf)))
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append(_strip_quotes("".join(buf)))
    return [i for i in items if i]


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse optional YAML frontmatter at the top of `content`.

    Returns (metadata_dict, body_without_frontmatter). If no frontmatter
    is present (or it's malformed), returns ({}, original content).
    """
    if not content.startswith("---"):
        return {}, content

    # Locate the closing `---` boundary on its own line.
    after_open = content[3:]
    m = re.search(r"^---\s*$", after_open, re.MULTILINE)
    if not m:
        return {}, content

    raw_block = after_open[: m.start()]
    body_start = 3 + m.end()
    # consume trailing newline after the closing boundary
    if body_start < len(content) and content[body_start] == "\n":
        body_start += 1
    body = content[body_start:]

    metadata: dict = {}
    for line_no, raw_line in enumerate(raw_block.splitlines(), start=1):
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            logger.debug("frontmatter line %d ignored (no colon): %r", line_no, raw_line)
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith("[") and value.endswith("]"):
            metadata[key] = _parse_inline_list(value)
        elif not value:
            metadata[key] = ""
        else:
            metadata[key] = _strip_quotes(value)
    return metadata, body


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _infer_doc_type(relative_path: str) -> str:
    """Infer document type from path."""
    parts = Path(relative_path).parts
    name = Path(relative_path).stem

    if name == "agents":
        return "agents"
    if name == "architecture":
        return "architecture"
    if name == "error-conventions":
        return "error-conventions"
    if name == "anti-patterns":
        return "anti-patterns"
    if name == "glossary":
        return "glossary"
    if "patterns" in parts:
        return "pattern"
    if "skills" in parts:
        return "skill"
    return "other"


def _is_excluded(relative_path: str) -> bool:
    for prefix in _EXCLUDED_PREFIXES:
        if relative_path.startswith(prefix):
            return True
    if relative_path in _EXCLUDED_TOP_LEVEL_FILES:
        return True
    return False


def _parse_docs(repo_root: Path) -> list[RuleDoc]:
    """Walk repo, load all .md files into RuleDoc list."""
    docs: list[RuleDoc] = []

    for md_file in repo_root.rglob("*.md"):
        relative = md_file.relative_to(repo_root)
        relative_str = relative.as_posix()

        if _is_excluded(relative_str):
            continue

        parts = relative.parts
        if len(parts) < 2:
            # Top-level .md not in our excluded set — surface it so authors
            # know it isn't being indexed.
            logger.warning(
                "Skipping top-level markdown file %s (not under a project directory)",
                relative_str,
            )
            continue

        project = parts[0]
        doc_relative = "/".join(parts[1:])
        doc_type = _infer_doc_type(doc_relative)
        name = relative.stem

        try:
            raw_content = md_file.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read %s: %s", md_file, e)
            continue

        metadata, body = _parse_frontmatter(raw_content)

        if doc_type == "other":
            logger.warning(
                "Doc %s/%s does not match a known type (agents/architecture/"
                "error-conventions/anti-patterns/glossary/patterns/skills); "
                "indexing as 'other'.",
                project,
                doc_relative,
            )

        docs.append(
            RuleDoc(
                project=project,
                relative_path=doc_relative,
                doc_type=doc_type,
                name=name,
                content=body,
                metadata=metadata,
            )
        )
        logger.debug("Loaded: %s / %s (%s)", project, doc_relative, doc_type)

    return docs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_rules_root() -> Path:
    """
    Parent of the mcp/ directory: repository root with project folders
    (e.g. integration-manager/).
    """
    root = _DEFAULT_RULES_ROOT
    if not root.is_dir():
        raise FileNotFoundError(
            f"Rules root does not exist or is not a directory: {root}",
        )
    return root


def load_store(repo_root: Path) -> RulesStore:
    """Load all rule docs from disk into memory."""
    docs = _parse_docs(repo_root)
    logger.info("Loaded %d rule docs from %s.", len(docs), repo_root)
    return RulesStore(docs=docs)


def bootstrap() -> RulesStore:
    """Resolve rules root and load. Call once at server startup."""
    repo_root = resolve_rules_root()
    return load_store(repo_root)
