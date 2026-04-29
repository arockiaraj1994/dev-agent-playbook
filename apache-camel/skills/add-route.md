---
title: Skill — Add a new Camel route
description: Step-by-step playbook for authoring a new YAML-DSL Camel route with DLQ wiring and tests.
type: skill
tags: [camel, route, yaml-dsl]
triggers: [add a route, new route, create a camel route, new connector]
see_also: [pattern:sftp-route, pattern:rest-producer, pattern:messaging-route, pattern:error-handling]
---

# Skill: Add a New Camel Route

**Trigger:** User asks to add, create, or implement a new integration route.

---

## Steps

1. **Identify the integration type**
   - Source system: SFTP, REST API, JMS queue, Kafka topic, database, timer?
   - Target system: same choices plus `direct:` to chain routes.
   - Message format: JSON, XML, CSV, binary?
   - Confirm with user if unclear — don't assume.

2. **Create the route file**
   - Path: `src/main/resources/camel/<domain>/<flow-name>.yaml`
   - One file = one integration flow.
   - Reference the appropriate pattern:
     - SFTP → `./patterns/sftp-route.md`
     - REST → `./patterns/rest-producer.md`
     - JMS / Kafka → `./patterns/messaging-route.md`

3. **Set a stable `routeId`**
   - Format: `<component>-<direction>-<domain>` — e.g. `sftp-inbound-payments`, `rest-post-invoices`.
   - Must be unique across all routes in the project.

4. **Externalize all config**
   - Add required property keys to `application.properties` backed by env vars.
   - Never use literal hostnames, ports, credentials, or URLs in route YAML.

5. **Define error handling**
   - Add `errorHandler` (dead-letter channel) at the top of the file.
   - Implement the DLQ consuming route — either in this file or in a shared `<domain>-error.yaml`.
   - Follow `./error-conventions.md` for retry policy values.

6. **Add a Processor bean (if transformation is needed)**
   - Create `src/main/java/.../processor/<FlowName>Processor.java`.
   - Processor calls a service bean for business logic — no business logic in the Processor itself.
   - Reference via `bean` step in YAML.

7. **Write tests**
   - Test the happy path: message consumed → transformed → delivered.
   - Test the error path: processing failure → DLQ receives message.
   - Use `MockEndpoint` to assert delivery without real external systems.
   - Use `NotifyBuilder` for async assertions — no `Thread.sleep`.

8. **Update `architecture.md`** if this route introduces a new external system class (new protocol or new third-party service not already documented).

---

## Constraints

- YAML DSL only.
- Credentials via env vars / Kubernetes Secrets only.
- DLQ route MUST be implemented — `direct:dlq-*` with no consumer = silent drop.
- Do not add new Maven dependencies without checking existing components first.
