---
title: Java standards — Apache Camel
description: Java 21 + Camel YAML DSL coding standards for routes, processors, and service beans.
language: java
tags: [java, standards, camel]
---

# Java standards — Apache Camel

## Language baseline

- Java 21. Use language features that improve clarity: `record`, `sealed`, `switch` patterns, `var` for obvious local types.
- Keep methods short — 20 lines is the working ceiling. Extract helpers when a method exceeds it.
- No boolean flag arguments. Split into separately named methods.
- Prefer immutable types (`record`, `final` fields) for DTOs and value objects.

## Naming

- Route IDs: `lowercase-kebab-case`, descriptive: `sftp-inbound-payments`, `rest-post-invoice`. No `route1`, `handler`, `process`.
- Property keys: dot-separated, namespaced: `sftp.payments.host`, `rest.invoice.url`.
- Class names match the role: `*Processor` for Camel processors, `*Service` for domain logic, `*Repository` for data access.

## Camel routes (YAML DSL)

- One file per integration flow. No mega-files mixing unrelated flows.
- Set `routeId` and a `description` when the purpose isn't obvious from the ID.
- Define `errorHandler` / `onException` / DLQ in each route.
- Use property placeholders for everything that varies between environments: hosts, ports, paths, credentials, feature flags.
- Indent consistently (2 spaces).

## Processors and service beans

- Camel `Processor` beans do ONE thing. They translate `Exchange` ↔ domain types and call a service.
- Service beans are Camel-free: they accept plain Java, return plain Java, and have no `@Inject ProducerTemplate` / `CamelContext`.
- Configuration via `@ConfigProperty` (Quarkus) or `@Value` (Spring) — never read system properties directly.

## Performance

- Don't block the Camel thread pool with synchronous I/O. Use async components, `threads` DSL, or a managed executor.
- For high-volume polling, tune `delay`, `maxMessagesPerPoll`, and `noop` deliberately rather than copy-pasting defaults.
- Prefer `split` + `aggregate` over loading whole payloads into memory.

## Logging

- SLF4J / JBoss Logging only. No `System.out.println`.
- Include `routeId`, message/file ID, exception message. Never the body if it could carry PII.

## Dependencies

- Before adding a new library, check whether an existing Camel component covers the need.
- New dependencies need a one-line justification in the PR description.
