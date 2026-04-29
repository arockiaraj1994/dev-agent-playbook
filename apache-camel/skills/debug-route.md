---
title: Skill — Debug a failing Camel route
description: Reproduce, isolate, and fix defects in an existing Camel route — DLQ checks, redelivery policy, error handler config.
type: skill
tags: [camel, debug, troubleshooting]
triggers: [debug a route, route is failing, messages are dropped, dlq filling up, fix camel bug]
see_also: [pattern:error-handling, pattern:sftp-route, language:java/testing]
---

# Skill: Debug a Failing Camel Route

**Trigger:** User reports a route is failing, messages are lost, or output is incorrect.

---

## Steps

1. **Check the logs first**
   - Look for `ERROR` lines with the `routeId` — every route error should log route ID, message ID, and exception.
   - If logs are missing context, the route is violating `./error-conventions.md` — add logging as part of the fix.
   - Common log pattern to search: `routeId=<id>` or the Camel exception class.

2. **Check if the DLQ is receiving messages**
   - If messages are disappearing, check whether the DLQ consuming route is implemented.
   - A `direct:dlq-*` endpoint with no consuming route silently drops messages.

3. **Reproduce in dev mode**
   - Quarkus: `mvn quarkus:dev` — the Camel dev UI shows live route topology, exchange traces, and endpoint stats at `/q/dev-ui`.
   - Spring Boot: enable `camel.management.enabled=true` and use JMX or `/actuator/camelroutes`.
   - Reduce `delay` on SFTP/timer consumers to speed up reproduction.

4. **Add a tracer (temporarily)**
   ```yaml
   - route:
       id: sftp-inbound-payments
       # ...
       steps:
         - log:
             message: "TRACE headers=${headers} body=${body}"
             loggingLevel: DEBUG
         - to:
             uri: "direct:transform-payments"
   ```
   Remove tracing before committing — never log sensitive payloads.

5. **Isolate the failing step**
   - Comment out steps after the suspected failure point.
   - Use `mock:` endpoint as a temporary sink to confirm messages arrive up to a given step.

6. **Check configuration**
   - Verify env vars are set: wrong placeholder → Camel treats it as a literal, causing connection failures.
   - Check `application.properties` for typos in property keys.

7. **Check the error handler config**
   - Is `maximumRedeliveries` set too low? Check if DLQ is receiving after the first failure.
   - Is `bridgeErrorHandler: true` set on SFTP/file consumers? Without it, consumer exceptions bypass the route error handler.

8. **Write a regression test**
   - Once the cause is found, add a test that fails without the fix and passes with it.
   - Test the specific error scenario — don't just add a happy-path test.

---

## Common Failure Patterns

| Symptom | Likely cause |
|---------|-------------|
| Messages disappear | DLQ consuming route not implemented |
| "No such endpoint" | Property placeholder not resolved — check env vars |
| Route never starts | Exception during route startup — check `@PostConstruct` / `RouteBuilder` for missing config |
| Transform produces empty body | Bean method returns `null` — check method return type |
| Retries don't happen | `bridgeErrorHandler` not set on consumer; or exception not caught by `onException` type |
| SFTP picks up same file repeatedly | `delete: false` and `noop: false` — set one or use an idempotent repository |
| Out-of-order messages | Parallel `concurrentConsumers` without ordering guarantee — reduce to 1 or use `resequencer` |
