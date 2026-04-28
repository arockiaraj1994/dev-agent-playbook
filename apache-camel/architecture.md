# Architecture — Apache Camel

This document describes the standard architecture for Apache Camel integration projects in this playbook.

---

## System Overview

Apache Camel is an **integration framework** that implements Enterprise Integration Patterns (EIPs). Projects built here follow a **route-centric** model: each integration flow is a Camel route, authored in **YAML DSL**, deployed on either **Quarkus** or **Spring Boot**.

**Core responsibilities:**

- Message routing between systems (SFTP, REST, messaging brokers, databases)
- Data transformation and enrichment (JSLT, Groovy, Java beans)
- Protocol mediation (HTTP, FTP/SFTP, JMS/AMQP, Kafka, database)
- Error handling, retries, and dead-letter queue (DLQ) management

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Integration framework | Apache Camel 4.x (YAML DSL) |
| Runtime (option A) | Quarkus 3.x — native-image ready, fast startup |
| Runtime (option B) | Spring Boot 3.x — wider ecosystem familiarity |
| Java | Java 21 |
| Build | Maven 3.9+ |
| Config | `application.properties` + env-variable-backed placeholders |
| Secret management | Kubernetes Secrets / Vault / env vars (never committed values) |
| Testing | JUnit 5 + `CamelTestSupport` / Quarkus test / WireMock |
| Observability | Micrometer metrics + Quarkus dev UI / Spring Boot Actuator |

---

## Route Structure

```
src/main/resources/camel/
  <domain>/
    <flow-name>.yaml        ← one file per integration flow
    <flow-name>-error.yaml  ← optional explicit error/DLQ routes
src/main/java/.../
  processor/                ← Camel Processor beans (transformation, enrichment)
  service/                  ← Domain logic (no Camel dependency)
  model/                    ← DTOs / value types
src/main/resources/
  application.properties    ← all config keys; values from env vars
```

---

## Messaging Topology

```
[External System A]          [External System B]
  SFTP / REST / MQ               REST / DB / MQ
       │                               ▲
       ▼                               │
[Camel Consumer Route]   ──►   [Transform / Enrich]   ──►   [Camel Producer Route]
       │                                                             │
       └──────────────────► [DLQ Route] ◄────────────────────────────┘
                                  │
                            [Alert / Persist]
```

---

## Service Boundaries

| Layer | Responsibility |
|-------|---------------|
| **Consumer route** | Poll or receive messages from external systems |
| **Transformer** | Convert format (XML→JSON, CSV→POJO, etc.) — Processor bean or JSLT |
| **Enricher** | Fetch additional data needed for routing decisions |
| **Producer route** | Deliver transformed messages to target systems |
| **Error / DLQ route** | Catch failed messages; persist, alert, and optionally replay |

Camel routes call **service beans** for business logic. Service beans have **no Camel dependency** — they accept plain Java types. This keeps logic testable without a Camel context.

---

## Key Design Decisions

- **YAML DSL only** — keeps routes readable by non-Java developers and toolable by Karavan.
- **One route file = one flow** — avoid mega-files that mix unrelated integrations.
- **Property placeholders everywhere** — `{{sftp.host}}` backed by env vars, never literals.
- **Explicit DLQ per domain** — don't rely on a global catch-all; each domain owns its failure path.
- **No Camel in service layer** — `Exchange`, `Message`, and `ProducerTemplate` stay in routes and processors only.

---

## Observability

- Route metrics (exchange count, failure rate, last exchange) via **Micrometer** → Prometheus.
- Distributed tracing via **OpenTelemetry** Camel extension (optional but recommended).
- Camel dev UI (Quarkus) shows live route topology, exchange traces, and endpoint stats in dev mode.
- Health checks: `camel.health.*` exposes liveness and readiness per route.

---

## Notes for Agents

- Routes use **YAML DSL** — never Java DSL unless the user explicitly says so.
- Config values come from `application.properties` backed by env vars — never commit real secrets.
- Service beans are plain Java — no `@Inject ProducerTemplate` in the service layer.
- DLQ routes must be implemented, not just referenced — a `direct:dlq` endpoint with no consumer is a silent message drop.
