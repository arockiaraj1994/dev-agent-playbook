---
title: Write a story
description: Author a user story under an existing PRD.
triggers: [write story, new story, user story]
see_also: [tool:playbook_start_requirement, tool:playbook_search_docs, core:guardrails]
---

# Workflow: write-story

1. Call `playbook_start_requirement(project="nexre", intent="…", type="story", prd="PRD-NNN")`.
2. Write User Story (As a… I want… so that…).
3. Add ≥3 acceptance criteria (`- [ ]` or Given/When/Then).
4. Fill `targets:` from the suggested standards links (edit, don't invent).
5. Set priority P0/P1/P2. Keep `draft` until the parent PRD is ready.
