"""
requirement_rules.py - Quality rules for PRDs and stories.

Status-aware severity:
  draft   → ALL rules soft (a PM must never break CI with a half-written PRD)
  approved / shipped → hard rules fire

`story.targets_resolve` is the cross-corpus check - the load-bearing rule of
the two-corpus design.
"""

from __future__ import annotations

import re
from pathlib import Path

from loader import RuleDoc

SEVERITY_HARD = "hard"
SEVERITY_SOFT = "soft"

VALID_STATUSES = frozenset({"draft", "approved", "shipped"})
VALID_PRIORITIES = frozenset({"P0", "P1", "P2"})

_USER_STORY_RE = re.compile(
    r"as a\s+.+?\s+I want\s+.+?\s+so that\s+.+?",
    re.IGNORECASE | re.DOTALL,
)
_CHECKBOX_RE = re.compile(r"^\s*-\s*\[[ xX]?\]\s+\S", re.MULTILINE)
_GIVEN_WHEN_THEN_RE = re.compile(
    r"\bGiven\b.+\bWhen\b.+\bThen\b",
    re.IGNORECASE | re.DOTALL,
)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_PRD_FOLDER_RE = re.compile(r"^(PRD-\d+)(?:-.*)?$")
_STORY_FILE_RE = re.compile(r"^(ST-\d+)(?:-.*)?$")


def _status(doc: RuleDoc) -> str:
    raw = doc.metadata.get("status", "draft")
    if isinstance(raw, str) and raw.strip() in VALID_STATUSES:
        return raw.strip()
    return "draft"


def _severity_for(doc: RuleDoc, intended: str) -> str:
    """Draft docs never hard-fail; approved/shipped keep intended severity."""
    if _status(doc) == "draft":
        return SEVERITY_SOFT
    return intended


def _has_section(content: str, heading: str) -> bool:
    target = heading.lower()
    for m in _H2_RE.finditer(content):
        if m.group(1).strip().lower() == target:
            return True
    return False


def _section_body(content: str, heading: str) -> str:
    target = heading.lower()
    matches = list(_H2_RE.finditer(content))
    for i, m in enumerate(matches):
        if m.group(1).strip().lower() == target:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            return content[start:end].strip()
    return ""


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _meta_str(doc: RuleDoc, key: str, default: str = "") -> str:
    v = doc.metadata.get(key)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return default


# ---------------------------------------------------------------------------
# Individual rules - each returns (rule_id, intended_severity, passed, message)
# ---------------------------------------------------------------------------


def _prd_rules(doc: RuleDoc, standards_projects: set[str], story_count: int) -> list[tuple]:
    results: list[tuple] = []
    folder = Path(doc.relative_path).parts[0] if doc.relative_path else ""
    folder_m = _PRD_FOLDER_RE.match(folder)
    folder_id = folder_m.group(1) if folder_m else ""
    meta_id = _meta_str(doc, "id") or doc.name

    results.append(
        (
            "prd.id_matches_folder",
            SEVERITY_HARD,
            bool(folder_id) and meta_id == folder_id,
            f"id '{meta_id}' matches folder prefix '{folder_id}'"
            if folder_id and meta_id == folder_id
            else f"id '{meta_id}' must match folder prefix (got folder '{folder}')",
        )
    )

    project_field = _meta_str(doc, "project") or doc.project
    results.append(
        (
            "prd.project_resolves",
            SEVERITY_HARD,
            project_field in standards_projects,
            f"project '{project_field}' exists under standards/"
            if project_field in standards_projects
            else f"project '{project_field}' not found under standards/",
        )
    )

    status = _meta_str(doc, "status", "draft")
    results.append(
        (
            "prd.status_valid",
            SEVERITY_HARD,
            status in VALID_STATUSES,
            f"status '{status}' is valid"
            if status in VALID_STATUSES
            else f"status must be one of {sorted(VALID_STATUSES)}",
        )
    )

    problem = _section_body(doc.content, "Problem")
    results.append(
        (
            "prd.has_problem",
            SEVERITY_HARD,
            _has_section(doc.content, "Problem") and _word_count(problem) >= 30,
            "Problem section present (≥30 words)"
            if _has_section(doc.content, "Problem") and _word_count(problem) >= 30
            else "Need ## Problem with ≥30 words",
        )
    )

    results.append(
        (
            "prd.has_goals",
            SEVERITY_HARD,
            _has_section(doc.content, "Goals"),
            "Goals section present" if _has_section(doc.content, "Goals") else "Need ## Goals",
        )
    )

    results.append(
        (
            "prd.has_non_goals",
            SEVERITY_HARD,
            _has_section(doc.content, "Non-Goals"),
            "Non-Goals section present"
            if _has_section(doc.content, "Non-Goals")
            else "Need ## Non-Goals (scope-creep insurance)",
        )
    )

    results.append(
        (
            "prd.has_stories",
            SEVERITY_HARD,
            story_count >= 1,
            f"Has {story_count} story/stories"
            if story_count >= 1
            else "Need ≥1 story under stories/",
        )
    )

    # Soft
    results.append(
        (
            "prd.has_success_metrics",
            SEVERITY_SOFT,
            _has_section(doc.content, "Success Metrics"),
            "Success Metrics present"
            if _has_section(doc.content, "Success Metrics")
            else "Consider adding ## Success Metrics",
        )
    )

    open_q = _section_body(doc.content, "Open Questions")
    has_blocking = bool(open_q) and _status(doc) == "approved"
    # Soft smell: approved with unresolved open questions
    results.append(
        (
            "prd.no_open_questions_when_approved",
            SEVERITY_SOFT,
            not has_blocking or "none" in open_q.lower() or len(open_q) < 20,
            "No blocking open questions at approved"
            if not has_blocking or "none" in open_q.lower() or len(open_q) < 20
            else "Approved PRD still has Open Questions - resolve or move to draft",
        )
    )

    results.append(
        (
            "prd.owner_set",
            SEVERITY_SOFT,
            bool(_meta_str(doc, "owner")),
            f"owner={_meta_str(doc, 'owner')}"
            if _meta_str(doc, "owner")
            else "Set owner: in frontmatter",
        )
    )
    return results


def _story_rules(
    doc: RuleDoc,
    standards_docs: list[RuleDoc],
    sibling_ids: set[str],
    parent_status: str | None,
) -> list[tuple]:
    results: list[tuple] = []
    stem = Path(doc.relative_path).stem
    file_m = _STORY_FILE_RE.match(stem)
    file_id = file_m.group(1) if file_m else ""
    meta_id = _meta_str(doc, "id") or doc.name

    results.append(
        (
            "story.id_matches_filename",
            SEVERITY_HARD,
            bool(file_id) and meta_id == file_id,
            f"id '{meta_id}' matches filename prefix '{file_id}'"
            if file_id and meta_id == file_id
            else f"id '{meta_id}' must match filename prefix (got '{stem}')",
        )
    )

    parts = Path(doc.relative_path).parts
    in_prd = (
        len(parts) == 3 and _PRD_FOLDER_RE.match(parts[0]) is not None and parts[1] == "stories"
    )
    results.append(
        (
            "story.in_prd_folder",
            SEVERITY_HARD,
            in_prd,
            "Story lives under PRD-*/stories/"
            if in_prd
            else f"Story path '{doc.relative_path}' is not under PRD-*/stories/",
        )
    )

    user_story = _section_body(doc.content, "User Story") or doc.content
    results.append(
        (
            "story.has_user_story",
            SEVERITY_HARD,
            bool(_USER_STORY_RE.search(user_story)),
            "User Story matches 'As a … I want … so that …'"
            if _USER_STORY_RE.search(user_story)
            else "Need ## User Story in 'As a … I want … so that …' form",
        )
    )

    ac = _section_body(doc.content, "Acceptance Criteria")
    checkboxes = _CHECKBOX_RE.findall(ac) if ac else []
    gwt_blocks = len(_GIVEN_WHEN_THEN_RE.findall(ac)) if ac else 0
    ac_ok = len(checkboxes) >= 3 or gwt_blocks >= 3
    results.append(
        (
            "story.has_acceptance_criteria",
            SEVERITY_HARD,
            ac_ok,
            f"Acceptance criteria: {len(checkboxes)} checkboxes / {gwt_blocks} G/W/T"
            if ac_ok
            else "Need ≥3 `- [ ]` items or Given/When/Then blocks under ## Acceptance Criteria",
        )
    )

    priority = _meta_str(doc, "priority")
    results.append(
        (
            "story.priority_valid",
            SEVERITY_HARD,
            priority in VALID_PRIORITIES,
            f"priority {priority} valid"
            if priority in VALID_PRIORITIES
            else f"priority must be one of {sorted(VALID_PRIORITIES)}",
        )
    )

    # Soft: targets resolve against standards
    targets = doc.metadata.get("targets") or []
    if not isinstance(targets, list):
        targets = []
    unresolved: list[str] = []
    std_by_type: dict[str, set[str]] = {}
    for s in standards_docs:
        if s.project != doc.project:
            continue
        std_by_type.setdefault(s.doc_type, set()).add(s.name)
        # Also index by stem for language-rules already using name=lang/doc
    for entry in targets:
        if not isinstance(entry, str) or ":" not in entry:
            unresolved.append(str(entry))
            continue
        kind, _, name = entry.partition(":")
        kind, name = kind.strip(), name.strip()
        type_map = {
            "pattern": "pattern",
            "skill": "skill",
            "workflow": "workflow",
            "language": "language-rules",
            "architecture": "architecture",
            "core": "guardrails",
            "gate": "gate",
            "gates": "gate",
        }
        dtype = type_map.get(kind)
        if dtype is None:
            unresolved.append(entry)
            continue
        names = std_by_type.get(dtype, set())
        # core:guardrails / core:definition-of-done
        if kind == "core":
            if name not in ("guardrails", "definition-of-done"):
                unresolved.append(entry)
            continue
        if kind == "architecture" and name in ("", "overview"):
            continue
        if name not in names and f"{name}" not in names:
            # language:kotlin/testing → name is already language-rules name
            if name not in names:
                unresolved.append(entry)

    results.append(
        (
            "story.targets_resolve",
            SEVERITY_SOFT,
            not unresolved,
            "All targets: resolve under standards/"
            if not unresolved
            else f"Unresolved targets: {unresolved}",
        )
    )

    depends = doc.metadata.get("depends_on") or []
    if not isinstance(depends, list):
        depends = []
    missing_deps = [
        d for d in depends if isinstance(d, str) and d.strip() and d.strip() not in sibling_ids
    ]
    results.append(
        (
            "story.depends_on_resolve",
            SEVERITY_SOFT,
            not missing_deps,
            "depends_on ids exist in same PRD"
            if not missing_deps
            else f"Unknown depends_on: {missing_deps}",
        )
    )

    # Circular depends - soft, simple self-ref check (full cycle needs graph)
    results.append(
        (
            "story.no_circular_depends",
            SEVERITY_SOFT,
            meta_id not in {d.strip() for d in depends if isinstance(d, str)},
            "No self-dependency"
            if meta_id not in {d.strip() for d in depends if isinstance(d, str)}
            else f"{meta_id} depends on itself",
        )
    )

    approved_under_draft = _status(doc) == "approved" and parent_status == "draft"
    results.append(
        (
            "story.approved_prd_when_approved",
            SEVERITY_SOFT,
            not approved_under_draft,
            "Parent PRD is approved/shipped (or story is draft)"
            if not approved_under_draft
            else "Approved story under a draft PRD is inconsistent",
        )
    )
    return results


def validate_requirement_docs(
    docs: list[RuleDoc],
    standards_docs: list[RuleDoc],
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Return (hard_errors, soft_warnings) as (project, category, message) tuples.

    Hard errors only fire for approved/shipped docs; draft failures are soft.
    """
    hard: list[tuple[str, str, str]] = []
    soft: list[tuple[str, str, str]] = []

    standards_projects = {d.project for d in standards_docs}
    prds = [d for d in docs if d.doc_type == "prd"]
    stories = [d for d in docs if d.doc_type == "story"]

    # Index stories by PRD folder
    stories_by_folder: dict[str, list[RuleDoc]] = {}
    for s in stories:
        folder = Path(s.relative_path).parts[0] if s.relative_path else ""
        stories_by_folder.setdefault((s.project, folder), []).append(s)

    prd_status: dict[tuple[str, str], str] = {}
    for prd in prds:
        folder = Path(prd.relative_path).parts[0]
        kids = stories_by_folder.get((prd.project, folder), [])
        prd_status[(prd.project, folder)] = _status(prd)
        for rule_id, intended, passed, message in _prd_rules(prd, standards_projects, len(kids)):
            sev = _severity_for(prd, intended)
            entry = (prd.project, rule_id, f"{prd.relative_path}: {message}")
            if passed:
                continue
            if sev == SEVERITY_HARD:
                hard.append(entry)
            else:
                soft.append(entry)

    for story in stories:
        folder = Path(story.relative_path).parts[0] if story.relative_path else ""
        siblings = stories_by_folder.get((story.project, folder), [])
        sibling_ids = {(_meta_str(s, "id") or s.name) for s in siblings}
        parent = prd_status.get((story.project, folder))
        for rule_id, intended, passed, message in _story_rules(
            story, standards_docs, sibling_ids, parent
        ):
            sev = _severity_for(story, intended)
            entry = (story.project, rule_id, f"{story.relative_path}: {message}")
            if passed:
                continue
            if sev == SEVERITY_HARD:
                hard.append(entry)
            else:
                soft.append(entry)

    return hard, soft
