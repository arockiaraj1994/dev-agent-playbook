---
title: Glossary — Apache Camel
description: Domain terms and Camel concepts used in routes, processors, and tests.
tags: [glossary, camel, terminology]
---

# Glossary — Apache Camel

Domain terms and Camel concepts. Use consistent terms in routes, logs, code, and comments.

---

| Term | Definition |
|------|------------|
| **Route** | A single integration flow defined in YAML DSL with a `from` (consumer) and one or more `steps` (processors + producers). |
| **Consumer** | The `from` endpoint of a route — listens for or polls messages (SFTP poll, REST listener, queue subscriber). |
| **Producer** | A `to` or `toD` step — sends a message to an external system or another route. |
| **Exchange** | The message container traveling through a route — holds `in`/`out` messages, headers, and properties. |
| **Message** | The body + headers inside an `Exchange`. |
| **Header** | Key-value metadata on a message. Camel sets standard headers per component (e.g. `CamelFileName`, `CamelHttpResponseCode`). |
| **Property** | Route-level metadata on an `Exchange` — scoped to the route lifetime, not forwarded to endpoints by default. |
| **EIP** | Enterprise Integration Pattern — reusable messaging patterns (Content-Based Router, Splitter, Aggregator, etc.) that Camel implements. |
| **Component** | A pluggable Camel extension that handles a protocol or technology — `camel-sftp`, `camel-http`, `camel-kafka`, etc. |
| **Endpoint URI** | Fully-qualified address of a component: `sftp://host:port/dir?option=value`. |
| **Direct** | `direct:name` — synchronous in-process channel between routes. Zero overhead, no threading. |
| **SEDA** | `seda:name` — asynchronous in-process queue with configurable thread pool. |
| **Dead Letter Channel (DLC)** | Error handler that routes failed messages to a `deadLetterUri` after max redeliveries. |
| **DLQ** | Dead Letter Queue — the destination (e.g. `direct:dlq-payments`) that receives messages the DLC routes. Always implement the consuming route. |
| **onException** | Camel DSL clause that catches a specific exception type and applies custom handling (retry policy, reroute, log). |
| **Processor** | Java class implementing `org.apache.camel.Processor` — receives and mutates an `Exchange`. Keep lean; delegate business logic to service beans. |
| **Bean** | A plain Java object referenced by Camel via `bean` step — Camel calls a method, passing the body or full `Exchange`. |
| **JSLT** | JSON Stream Language for Transformation — Camel's `jslt` component for JSON-to-JSON mapping. |
| **DataFormat** | Camel marshalling/unmarshalling extension — `json-jackson`, `jaxb`, `csv`, `avro`, etc. |
| **Splitter** | EIP that splits a single message into multiple sub-messages for parallel or sequential processing. |
| **Aggregator** | EIP that collects related messages and combines them into one (e.g. collect all lines of a batch). |
| **Content-Based Router (CBR)** | `choice` / `when` / `otherwise` — routes messages to different endpoints based on content. |
| **Wire Tap** | Sends a copy of the message to a secondary endpoint without affecting the main flow. |
| **Enrich** | Fetches additional data from an external resource and merges it into the current message. |
| **NotifyBuilder** | Test utility that waits for a condition on exchanges (completed, failed, to a given endpoint) — use instead of `Thread.sleep`. |
| **MockEndpoint** | Test endpoint that records received exchanges; supports assertions on count, body, and headers. |
| **RouteId** | Stable string identifier for a route — used in logs, metrics, and error tracking. Always set explicitly. |
| **bridgeErrorHandler** | Consumer option (`bridgeErrorHandler=true`) that routes consumer-level exceptions through the route's error handler instead of throwing immediately. |
| **YAML DSL** | Camel's declarative route format in `.yaml` files — the standard DSL for this playbook. |
| **Quarkus** | Fast Java runtime with native-image support; preferred runtime for new Camel services. |
| **Spring Boot** | Alternative Java runtime for Camel; used when team familiarity or ecosystem demands it. |
| **Micrometer** | Metrics facade used by both Quarkus and Spring Boot — exposes Camel route metrics to Prometheus. |
