---
title: SFTP Inbound/Outbound Route
type: pattern
tags: [camel, sftp, file, integration]
---

# Pattern: SFTP Route

Standard pattern for polling files from SFTP and delivering processed output back.

---

## Rules

- YAML DSL only. Never Java DSL.
- Always set `routeId`.
- Always externalize credentials via config properties backed by env vars — never literals.
- Always set `bridgeErrorHandler: true` on the consumer so file-level errors flow through the route's error handler.
- Always define a DLQ route for the domain — never reference `direct:dlq-*` without implementing the consumer.

---

## Canonical SFTP Inbound Route

```yaml
- errorHandler:
    deadLetterChannel:
      deadLetterUri: "direct:dlq-{{domain}}"
      maximumRedeliveries: 3
      redeliveryDelay: 2000
      backOffMultiplier: 2
      useExponentialBackOff: true
      retryAttemptedLogLevel: WARN
      retriesExhaustedLogLevel: ERROR

- route:
    id: sftp-inbound-{{domain}}
    from:
      uri: "sftp://{{sftp.host}}:{{sftp.port}}/{{sftp.inbound.dir}}"
      parameters:
        username: "{{sftp.username}}"
        password: "{{sftp.password}}"
        delay: 5000
        maxMessagesPerPoll: 10
        delete: true
        noop: false
        sortBy: "file:modified"
        bridgeErrorHandler: true
    steps:
      - log:
          message: "Received: ${header.CamelFileName} size=${header.CamelFileLength}"
          loggingLevel: INFO
      - to:
          uri: "direct:transform-{{domain}}"
```

---

## Canonical SFTP Outbound Route

```yaml
- route:
    id: sftp-outbound-{{domain}}
    from:
      uri: "direct:outbound-{{domain}}"
    steps:
      - log:
          message: "Sending: ${header.CamelFileName}"
          loggingLevel: INFO
      - to:
          uri: "sftp://{{sftp.host}}:{{sftp.port}}/{{sftp.outbound.dir}}"
          parameters:
            username: "{{sftp.username}}"
            password: "{{sftp.password}}"
            fileName: "${header.CamelFileName}"
```

---

## DLQ Route (MUST implement)

```yaml
- route:
    id: dlq-{{domain}}
    from:
      uri: "direct:dlq-{{domain}}"
    steps:
      - log:
          message: "DLQ [{{domain}}]: file=${header.CamelFileName} error=${exception.message}"
          loggingLevel: ERROR
      - bean:
          ref: dlqPersistenceService
          method: persist
```

---

## Required Config Properties

```properties
# application.properties
sftp.host=${SFTP_HOST}
sftp.port=${SFTP_PORT:22}
sftp.username=${SFTP_USERNAME}
sftp.password=${SFTP_PASSWORD}
sftp.inbound.dir=${SFTP_INBOUND_DIR}
sftp.outbound.dir=${SFTP_OUTBOUND_DIR}
```

---

## Error Scenarios

| Scenario | Behaviour |
|----------|-----------|
| Connection failure | Retry 3x with exponential backoff, then DLQ |
| Permission denied | Log ERROR, no retry, route to DLQ |
| File not found (noop=false) | Log WARN, skip — do not throw |
| Transform failure | Preserve original file, route to DLQ |
