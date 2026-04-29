"""
loader.py — Loads all markdown rule docs from disk into memory.

Path-first dispatch: doc_type is inferred from the doc's path inside the
project directory, not its filename alone. The supported layout per project:

    <project>/
      AGENTS.md
      INDEX.md
      README.md                     (skipped — human-only)
      core/{guardrails,definition-of-done,glossary}.md
      architecture/overview.md
      architecture/decisions/<n>.md
      languages/<lang>/{standards,testing,anti-patterns}.md
      patterns/<n>.md
      skills/<n>.md
      workflows/<n>.md
      gates/README.md               (+ gates/scripts/*.sh — listed in metadata only)

Optional YAML frontmatter is parsed (small dependency-free subset: scalar
strings, inline list of strings).
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

# Top-level dirs/files inside the rules repo that are not project rules.
_EXCLUDED_PREFIXES = ("mcp/", ".git/", ".github/", "scripts/", ".venv/")
_EXCLUDED_TOP_LEVEL_FILES = {
    "README.md",
    "CONTRIBUTING.md",
    "TEMPLATE.md",
    "CHANGELOG.md",
}

# Files inside a project that are intentionally not indexed (human-only).
_EXCLUDED_PROJECT_FILES = {"README.md"}


# All recognized doc types. Used by tools and validators.
KNOWN_DOC_TYPES = (
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


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RuleDoc:
    project: str
    relative_path: str
    doc_type: str
    name: str
    content: str
    metadata: dict = field(default_factory=dict)


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


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_inline_list(raw: str) -> list[str]:
    """Parse `[a, b, "c d"]` into ["a", "b", "c d"]. Bare strings allowed."""
    inner = raw.strip()[1:-1]
    if not inner.strip():
        return []
    items: list[str] = []
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

    after_open = content[3:]
    m = re.search(r"^---\s*$", after_open, re.MULTILINE)
    if not m:
        return {}, content

    raw_block = after_open[: m.start()]
    body_start = 3 + m.end()
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
# Path-first doc-type inference
# ---------------------------------------------------------------------------


def _infer_doc_type_and_name(relative_path: str) -> tuple[str, str]:
    """
    Infer (doc_type, name) from a path inside a project directory.

    `name` is the canonical identifier callers pass to fetch tools (without
    `.md`). For language-rules it is `<lang>/<doc>` (e.g. `java/standards`).

    Returns ("other", <stem>) for paths that don't fit the layout — these
    will be flagged as errors by the validator.
    """
    parts = Path(relative_path).parts
    stem = Path(relative_path).stem

    # Top-of-project files
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
        # languages/<lang>/<doc>.md
        if len(parts) == 3:
            lang = parts[1]
            doc = stem
            return "language-rules", f"{lang}/{doc}"
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


# Public alias retained for tests / callers that only need the type.
def _infer_doc_type(relative_path: str) -> str:
    return _infer_doc_type_and_name(relative_path)[0]


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------


def _is_excluded(relative_path: str) -> bool:
    for prefix in _EXCLUDED_PREFIXES:
        if relative_path.startswith(prefix):
            return True
    if relative_path in _EXCLUDED_TOP_LEVEL_FILES:
        return True
    # Per-project README.md (e.g. apache-camel/README.md) is human-only.
    parts = Path(relative_path).parts
    if len(parts) == 2 and parts[1] in _EXCLUDED_PROJECT_FILES:
        return True
    return False


# ---------------------------------------------------------------------------
# Walk + parse
# ---------------------------------------------------------------------------


def _list_gate_scripts(project_root: Path) -> list[str]:
    scripts_dir = project_root / "gates" / "scripts"
    if not scripts_dir.is_dir():
        return []
    return sorted(p.name for p in scripts_dir.iterdir() if p.is_file())


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
            logger.warning(
                "Skipping top-level markdown file %s (not under a project directory)",
                relative_str,
            )
            continue

        project = parts[0]
        doc_relative = "/".join(parts[1:])
        doc_type, name = _infer_doc_type_and_name(doc_relative)

        try:
            raw_content = md_file.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read %s: %s", md_file, e)
            continue

        metadata, body = _parse_frontmatter(raw_content)

        # Inject derived metadata
        if doc_type == "language-rules":
            # languages/<lang>/<doc>.md — store the language code.
            metadata.setdefault("language", parts[1] if parts[0] == "languages" else "")
            # parts here are project-relative; the language is parts[1] (after 'languages/').
            lang_parts = Path(doc_relative).parts
            if len(lang_parts) >= 2 and lang_parts[0] == "languages":
                metadata["language"] = lang_parts[1]

        if doc_type == "gate":
            scripts = _list_gate_scripts(repo_root / project)
            if scripts:
                metadata["gate_scripts"] = scripts

        if doc_type == "other":
            logger.warning(
                "Doc %s/%s does not match the expected layout; "
                "indexing as 'other' (validator will flag this).",
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
    """Parent of the mcp/ directory."""
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
