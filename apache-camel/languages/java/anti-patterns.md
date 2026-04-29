---
title: Java anti-patterns — Apache Camel
description: Mistakes to avoid when writing Camel routes, processors, and service beans in Java.
language: java
tags: [java, camel, anti-patterns]
---

# Anti-Patterns — Apache Camel

Read this BEFORE writing any code. Violating these causes silent failures, security holes, and unmaintainable routes.

---

## ROUTES & DSL

❌ DO NOT use Java DSL for routes — **YAML DSL only** unless explicitly instructed.

❌ DO NOT put multiple unrelated flows in one route file.  
   → One file = one integration flow.

❌ DO NOT skip `routeId`.  
   → Without it, logs and metrics are unidentifiable.

❌ DO NOT use hardcoded URIs or connection strings in route YAML.  
   → BAD: `uri: "sftp://prod-server:22/inbound"`  
   → GOOD: `uri: "sftp://{{sftp.host}}:{{sftp.port}}/{{sftp.dir}}"`

❌ DO NOT assume a global base error handler exists.  
   → Define `errorHandler` or `onException` in every consumer route.

❌ DO NOT leave a `direct:dlq` endpoint with no consuming route.  
   → Messages will be silently dropped. Always implement the DLQ route.

❌ DO NOT use unlimited redeliveries.  
   → `maximumRedeliveries: -1` causes runaway retry storms in production.

❌ DO NOT block the Camel thread pool with long synchronous operations.  
   → Use `threads` DSL, async components, or offload to a service bean with a managed executor.

---

## CONFIGURATION & SECRETS

❌ DO NOT hardcode credentials, tokens, or URLs as literal values in YAML or properties files.  
   → Use env-variable-backed placeholders: `{{env:SFTP_PASSWORD}}`.

❌ DO NOT commit `.env` files or files containing real secrets.

❌ DO NOT use a hardcoded `http://` endpoint for non-local production targets.  
   → TLS required. Use `https://`.

---

## ERROR HANDLING

❌ DO NOT use empty `doCatch` blocks.  
   → Silent swallowing makes debugging impossible.

❌ DO NOT return fake success responses when processing fails.

❌ DO NOT log message body content at any level if it may contain PII, card data, or credentials.

❌ DO NOT catch `Throwable` and continue — it masks JVM-level errors.

❌ DO NOT retry `4xx` HTTP errors (except `429`).  
   → A 400/404 from upstream won't fix itself with retries.

---

## TESTING

❌ DO NOT write tests that sleep to wait for async routes.  
   → Use `NotifyBuilder` or `MockEndpoint.assertIsSatisfied(timeout)`.

❌ DO NOT test without covering the DLQ / error path.

❌ DO NOT use `MockEndpoint` for internal bean logic — unit test beans directly.

❌ DO NOT write tests that only assert message count without checking content.

---

## JAVA / QUARKUS / SPRING BOOT

❌ DO NOT use `System.out.println` for logging — use SLF4J / JBoss Logging.

❌ DO NOT put business logic in Camel `Processor` classes — delegate to a service bean.

❌ DO NOT inject `ProducerTemplate` or `CamelContext` into service layer beans.  
   → Service beans must be Camel-free for testability.

❌ DO NOT mutate database schema by hand — use Flyway migrations if you add a SQL store.

❌ DO NOT add a new dependency without checking if an existing Camel component covers the need.

---

## STRUCTURAL

❌ DO NOT create god-routes that handle multiple unrelated message types with branching `choice`.  
   → Split into separate routes per type.

❌ DO NOT leave debugging residue: `_v2`, `_old`, `_test` in route IDs or file names.

❌ DO NOT over-engineer.  
   → No framework-within-a-framework for routing decisions that a simple `choice` handles.
