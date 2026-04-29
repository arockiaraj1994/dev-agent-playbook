---
title: Workflow — Bug fix
description: Reproducing, isolating, and fixing a defect in an existing route.
triggers: [bug, fix a bug, debug a route, route is failing, messages are dropped, dlq filling up]
gates: [verify-java]
see_also: [skill:debug-route, pattern:error-handling, language:java/testing]
---

# Workflow — Bug fix

Use this when the user reports broken behavior in an existing route.

## Steps

1. **Reproduce first.** Get the failing input (message, headers, file). If unavailable, ask. Don't speculate from logs alone.
2. **Isolate the route.** Find the `routeId` in logs / metrics. Read the YAML and any `Processor` / service bean it calls.
3. **Diagnose with the debug-route skill.** See `skills/debug-route.md` for the standard checks: error handler config, DLQ implementation, redelivery policy, property placeholders.
4. **Hypothesise → minimal fix.** Change ONLY the broken behavior. Don't refactor surrounding code. Don't rename things.
5. **Add a regression test.** The test must FAIL before the fix and PASS after. Cover the original failing input.
6. **Verify error path is still handled.** Re-check that the DLQ route still receives malformed messages.
7. **Run the gate.** `bash gates/scripts/verify-java.sh`.
8. **Write the commit.** Title = the fix. Body = WHY the bug happened (root cause), not just what changed.

## Common root causes (check these before going deeper)

- Missing `errorHandler` or `onException` on a consumer route.
- `direct:dlq-*` referenced but no consuming route → silent drop.
- Hardcoded URI instead of placeholder, then config changed in another env.
- Unlimited or zero `maximumRedeliveries`.
- Synchronous I/O blocking the Camel pool under load.
- Logging the body where PII was redacted upstream — privacy bug, not a behavior bug.
