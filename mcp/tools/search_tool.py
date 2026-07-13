"""tools/search_tool.py - find_rules tool.

One tool, two modes:

 - No `query`  → list mode. Every rule doc in the project with its path,
    doc type, title, summary, and `triggers:` phrases. Replaces the old
    `list_rule_docs` and `get_index` tools.
 - With `query` → search mode. BM25 across the corpus, ranked snippets.
    Replaces the old `search_rules`.

Only search mode writes `ctx.query` / `ctx.top_result_*`, so browsing the
catalogue does not pollute the dashboard's search analytics.
"""

from __future__ import annotations

from mcp.types import TextContent, Tool

from loader import KNOWN_DOC_TYPES, RuleDoc, RulesStore
from search import RulesSearchEngine

from .docs import _canonical_project

DEFINITIONS: list[Tool] = [
    Tool(
        name="find_rules",
        description=(
            "Discover rule docs for a project. Omit `query` to list every doc "
            "with its type, title, summary, and trigger phrases. Pass `query` "
            "to BM25-search the corpus for cross-cutting questions or when you "
            "don't know which doc to fetch - headings and frontmatter title/tags "
            "are weighted 2× over body, and results are ranked snippets with "
            "source path and parent heading. Default corpus is standards; pass "
            "corpus=requirements or corpus=all to include PRDs/stories."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": (
                        "Basename of the user's current workspace directory "
                        "(case-insensitive match to standards/). "
                        "NEVER invent another project."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Optional - keywords or natural language. Omit to list "
                        "all docs instead of searching."
                    ),
                },
                "doc_type": {
                    "type": "string",
                    "description": 'Optional - restrict to a doc type (e.g. "pattern").',
                    "enum": list(KNOWN_DOC_TYPES),
                },
                "corpus": {
                    "type": "string",
                    "description": (
                        "Which corpus to search. Default: standards (preserves legacy behavior)."
                    ),
                    "enum": ["standards", "requirements", "all"],
                    "default": "standards",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Search mode only. Max results. Default: 10.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["project"],
        },
    ),
]

_NAMES = {"find_rules"}


def _doc_title(doc: RuleDoc) -> str:
    t = doc.metadata.get("title")
    if isinstance(t, str) and t.strip():
        return t.strip()
    for line in doc.content.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
        if s and not s.startswith("---"):
            break
    return doc.name


def _doc_summary(doc: RuleDoc, max_len: int = 200) -> str:
    desc = doc.metadata.get("description")
    if isinstance(desc, str) and desc.strip():
        return desc.strip()[:max_len]
    for line in doc.content.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("---"):
            continue
        if s.startswith(">"):
            continue
        return s[:max_len]
    return ""


def _doc_triggers(doc: RuleDoc) -> list[str]:
    raw = doc.metadata.get("triggers") or []
    if not isinstance(raw, list):
        return []
    return [t.strip() for t in raw if isinstance(t, str) and t.strip()]


async def dispatch(
    name: str,
    arguments: dict,
    ctx: object,
    store: RulesStore,
    engine: RulesSearchEngine,
) -> list[TextContent] | None:
    if name not in _NAMES:
        return None

    project_raw = (arguments.get("project") or "").strip()
    query = (arguments.get("query") or "").strip()
    doc_type = arguments.get("doc_type") or None
    corpus = (arguments.get("corpus") or "standards").strip()
    if corpus not in ("standards", "requirements", "all"):
        corpus = "standards"

    known = list(store.projects(corpus=None))
    project = _canonical_project(project_raw, known)
    if project is None:
        ctx.status = "not_found"  # type: ignore[attr-defined]
        return [
            TextContent(
                type="text",
                text=(
                    f"Project '{project_raw}' not found. "
                    "`project` must be the basename of your current workspace "
                    "directory. Call list_projects to see valid names."
                ),
            )
        ]

    ctx.corpus = corpus

    if not query:
        return _list_mode(ctx, store, project, doc_type, corpus)
    return _search_mode(ctx, engine, project, query, doc_type, arguments.get("top_k", 10), corpus)


def _list_mode(
    ctx: object,
    store: RulesStore,
    project: str,
    doc_type: str | None,
    corpus: str,
) -> list[TextContent]:
    corpus_filter: str | None = None if corpus == "all" else corpus
    if doc_type:
        docs = store.of_type(project, doc_type, corpus=corpus_filter)
    else:
        docs = store.for_project(project, corpus=corpus_filter)
    if not docs:
        ctx.status = "empty"  # type: ignore[attr-defined]
        type_clause = f" of type '{doc_type}'" if doc_type else ""
        return [
            TextContent(
                type="text",
                text=f"No rule docs{type_clause} for project '{project}' (corpus={corpus}).",
            )
        ]

    lines: list[str] = []
    for d in sorted(docs, key=lambda x: (x.corpus, x.doc_type, x.relative_path)):
        entry = f"- **{d.relative_path}** ({d.doc_type}, {d.corpus}) - *{_doc_title(d)}*"
        summary = _doc_summary(d)
        if summary:
            entry += f"\n  {summary}"
        triggers = _doc_triggers(d)
        if triggers:
            entry += "\n  _Triggers:_ " + ", ".join(f"`{t}`" for t in triggers)
        lines.append(entry)
    return [TextContent(type="text", text="\n".join(lines))]


def _search_mode(
    ctx: object,
    engine: RulesSearchEngine,
    project: str,
    query: str,
    doc_type: str | None,
    raw_top_k: object,
    corpus: str,
) -> list[TextContent]:
    try:
        top_k = int(raw_top_k)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        top_k = 10
    top_k = max(1, min(50, top_k))

    ctx.query = query  # type: ignore[attr-defined]
    results = engine.search(
        query=query,
        project=project,
        doc_type=doc_type,
        top_k=top_k,
        corpus=corpus,
    )
    if not results:
        ctx.status = "empty"  # type: ignore[attr-defined]
        return [TextContent(type="text", text=f"No results found for query: '{query}'")]

    top = results[0]
    ctx.top_result_path = f"{top.project}/{top.relative_path}"  # type: ignore[attr-defined]
    ctx.top_result_score = top.score  # type: ignore[attr-defined]

    lines = []
    for i, r in enumerate(results, 1):
        heading_str = f" - under heading: *{r.heading}*" if r.heading else ""
        lines.append(
            f"### {i}. [{r.corpus}] {r.project}/{r.relative_path}  "
            f"(type: {r.doc_type}, score: {r.score}){heading_str}\n\n"
            f"{r.snippet}\n"
        )
    return [TextContent(type="text", text="\n---\n".join(lines))]
