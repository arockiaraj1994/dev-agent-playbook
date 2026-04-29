---
title: Workflow — Refactor
description: Restructuring routes, processors, or service code without changing observable behavior.
triggers: [refactor, restructure, cleanup, simplify, extract, split a route]
gates: [verify-java]
see_also: [language:java/standards, language:java/anti-patterns, pattern:messaging-route]
---

# Workflow — Refactor

Use this when the goal is internal cleanliness, not new behavior or fixed bugs.

## Steps

1. **Confirm the intent is pure refactor.** If the user also wants behavior changes, split into two PRs — refactor first, then behavior change. They review differently.
2. **Lock down behavior with tests.** Before changing structure, ensure the existing tests cover the behavior you're about to move. Add characterization tests if coverage is thin.
3. **Pick the target shape.** Read `languages/java/standards.md` and the relevant pattern doc. Don't invent a new structure when an existing pattern fits.
4. **Move in small steps.** Each commit on the branch should keep tests green. Avoid one giant rewrite commit.
5. **Verify no behavior drift.** Run the full suite after each step. If a test breaks, revert that step and rethink.
6. **Run the gate.** `bash gates/scripts/verify-java.sh`.
7. **Diff review.** Most lines should be moves/renames, not new logic. If you see new conditionals or new error paths, the refactor crossed into behavior change — split it out.

## Refactor candidates worth doing

- A route file containing two unrelated flows → split into two files.
- Business logic inside a `Processor` → extract to a Camel-free service bean.
- Repeated `errorHandler` blocks copied across routes → factor into a route template / RouteConfiguration.
- Hardcoded URIs that crept in over time → replace with property placeholders.

## Refactor candidates to skip

- Renaming a route ID for aesthetics (breaks logs, metrics, and dashboards).
- Changing the build tool, JVM version, or framework version under the banner of "refactor."
- Introducing a new abstraction layer with a single implementation.
