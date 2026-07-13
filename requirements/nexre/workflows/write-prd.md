---
title: Write a PRD
description: Author a product requirements document for NexRe.
triggers: [write prd, new prd, product requirements]
see_also: [tool:start_requirement, tool:list_requirements, core:guardrails]
---

# Workflow: write-prd

1. Call `start_requirement(project="nexre", intent="…", type="prd")`.
2. Fill Problem (≥30 words), Goals, Non-Goals, Success Metrics.
3. Keep status `draft` until stories exist and open questions are resolved.
4. Flip to `approved` only when ready for engineering handoff.
