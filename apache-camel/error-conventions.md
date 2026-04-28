# Error Conventions — Apache Camel

---

## General Rules (Non-Negotiable)

- Every consumer route MUST define a dead-letter channel or `onException` block.
- Never swallow exceptions silently. No empty `doTry/doCatch` with no action.
- Log with context on every error — route ID, message ID, body summary (no PII), exception message.
- Use exponential backoff for retries. Never unlimited retries on a production route.
- Crash early on misconfiguration (missing required properties) — fail at startup, not mid-flow.

---

## Error Handling in YAML DSL

### Dead-letter channel (route-level default)

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
    id: sftp-inbound-payments
    from:
      uri: "sftp://{{sftp.payments.host}}:{{sftp.payments.port}}/{{sftp.payments.dir}}"
      parameters:
        username: "{{sftp.payments.username}}"
        password: "{{sftp.payments.password}}"
        bridgeErrorHandler: true
    steps:
      - to:
          uri: "direct:transform-payments"
```

### `onException` for specific types

```yaml
- onException:
    exception:
      - "java.io.IOException"
    redeliveryPolicy:
      maximumRedeliveries: 5
      redeliveryDelay: 3000
      useExponentialBackOff: true
    handled:
      constant: true
    steps:
      - log:
          message: "IO failure on route ${routeId}, file ${header.CamelFileName}: ${exception.message}"
          loggingLevel: ERROR
      - to:
          uri: "direct:dlq-payments"
```

---

## DLQ Route (MUST be implemented)

```yaml
- route:
    id: dlq-payments
    from:
      uri: "direct:dlq-payments"
    steps:
      - log:
          message: "DLQ [payments]: routeId=${routeId} msgId=${header.CamelMessageId} error=${exception.message}"
          loggingLevel: ERROR
      - bean:
          ref: dlqPersistenceService
          method: persist
```

A `direct:dlq` endpoint with no consuming route = silent message drop. Always implement the DLQ route.

---

## Log Message Format

```
[LEVEL] routeId=<id> msgId=<id> file=<name> error=<message>
```

**Include:** route ID, message/file identifier, exception message (never full stack in WARN — full stack in ERROR only if actionable).

**Exclude from logs:** message payload content that may contain PII, credentials, card numbers, or sensitive financial data.

```yaml
# GOOD
- log:
    message: "Transform failed: routeId=${routeId} file=${header.CamelFileName} error=${exception.message}"
    loggingLevel: ERROR

# BAD — logs payload (may contain PII)
- log:
    message: "Failed: body=${body}"
    loggingLevel: ERROR
```

---

## HTTP Error Mapping (REST producers)

| HTTP status received | Action |
|----------------------|--------|
| `4xx` (client error) | Log ERROR, route to DLQ — do not retry (likely invalid message) |
| `429` (rate limit) | Retry with backoff |
| `5xx` (server error) | Retry with backoff up to max, then DLQ |
| Timeout / connection error | Retry with backoff up to max, then DLQ |

Use the `http4` / `vertx-http` component's `throwExceptionOnFailure=true` (default) so non-2xx responses throw and trigger `onException`.

---

## SFTP Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Connection failure | Retry with exponential backoff (3–5 attempts), then DLQ or alert |
| File not found | Log WARN, skip — do not throw unless required by business rules |
| Permission denied | Log ERROR, no retry, alert |
| Transform failure | Route to DLQ with original file preserved |

---

## Startup Failures (Configuration)

Fail fast if required config is missing. Do not silently substitute defaults for things like credentials or URLs.

```java
// In a @PostConstruct or RouteBuilder:
Objects.requireNonNull(sftpHost, "sftp.payments.host must be set");
```

Or use Quarkus `@ConfigProperty(name = "...", defaultValue = "")` combined with a startup check bean.

---

## What NOT to do

❌ Empty catch / doCatch blocks — they hide failures.  
❌ Returning a fake success body when processing fails — callers won't know.  
❌ Logging the full message body at ERROR level — PII risk.  
❌ Unlimited redeliveries — runaway retry storms.  
❌ A `direct:dlq` with no consumer route — silent drop.  
❌ Catching `Throwable` and continuing — masks bugs.
