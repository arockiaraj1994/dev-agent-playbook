---
title: Definition of Done — Apache Camel
description: Tests + lint + security gates that must pass before a task ships.
tags: [done, testing, gates]
---

# Definition of Done — Apache Camel

A change is done when ALL of the following hold. The `verify-java.sh` gate
runs the mechanical checks; the rest are author responsibilities.

## Mechanical (run via `gates/scripts/verify-java.sh`)

- [ ] Code compiles: `mvn -q -DskipTests verify`.
- [ ] Static analysis passes: `mvn -q spotbugs:check` (or project-configured equivalent).
- [ ] Format / lint passes: `mvn -q spotless:check` (or `checkstyle:check`).
- [ ] All tests pass: `mvn -q test`.
- [ ] No high/critical findings from dependency scan: `mvn -q dependency-check:check` (when configured).

## Functional

- [ ] Every new or changed route has a `routeId`.
- [ ] Every consumer route has an `errorHandler` / `onException` and the DLQ route is implemented.
- [ ] No literal hosts, ports, paths, or credentials in YAML — only `{{property.placeholders}}`.
- [ ] All new config keys appear in `application.properties` with env-var fallback.
- [ ] Tests cover the success path AND the error / DLQ path.
- [ ] Tests use `NotifyBuilder` / `MockEndpoint.assertIsSatisfied(timeout)` — no `Thread.sleep`.

## Observability

- [ ] Errors logged with `routeId`, message identifier, and exception message — never the full payload.
- [ ] Metrics exposed via Micrometer (route count, failure count, latency).

## Security

- [ ] No secrets in code, YAML, properties, or commit history.
- [ ] All non-local HTTP endpoints use TLS.
- [ ] Dependency updates reviewed for CVE impact when prompted by the scanner.

## Review

- [ ] Diff is minimal — no unrelated changes.
- [ ] Commit message explains WHY, not just WHAT.
- [ ] If the change touches an integration contract, the corresponding consumer/producer team is notified.
