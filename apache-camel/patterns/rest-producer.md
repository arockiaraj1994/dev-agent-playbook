---
title: REST Producer Route
type: pattern
tags: [camel, rest, http, integration]
---

# Pattern: REST Producer Route

Standard pattern for calling an external REST API from a Camel route.

---

## Rules

- Use `vertx-http` (Quarkus) or `http` (Spring Boot) component — prefer the runtime-native HTTP component.
- Always set `throwExceptionOnFailure=true` (default) so non-2xx responses trigger `onException`.
- Never hardcode URLs — use property placeholders.
- Set `Content-Type` and `Accept` headers explicitly.
- Retry on 5xx and timeouts. Do NOT retry on 4xx (except 429).

---

## Canonical REST POST Route

```yaml
- onException:
    exception:
      - "org.apache.camel.http.base.HttpOperationFailedException"
    onWhen:
      simple: "${exception.statusCode} >= 500"
    redeliveryPolicy:
      maximumRedeliveries: 3
      redeliveryDelay: 2000
      useExponentialBackOff: true
    handled:
      constant: false

- route:
    id: rest-post-{{domain}}
    from:
      uri: "direct:send-{{domain}}"
    steps:
      - setHeader:
          name: "Content-Type"
          constant: "application/json"
      - setHeader:
          name: "CamelHttpMethod"
          constant: "POST"
      - to:
          uri: "{{api.{{domain}}.url}}"
          parameters:
            throwExceptionOnFailure: true
            connectTimeout: 5000
            socketTimeout: 30000
      - log:
          message: "POST {{domain}} response: ${header.CamelHttpResponseCode}"
          loggingLevel: INFO
```

---

## Handling 429 Rate Limit

```yaml
- onException:
    exception:
      - "org.apache.camel.http.base.HttpOperationFailedException"
    onWhen:
      simple: "${exception.statusCode} == 429"
    redeliveryPolicy:
      maximumRedeliveries: 5
      redeliveryDelay: 10000
      useExponentialBackOff: true
    handled:
      constant: true
    steps:
      - log:
          message: "Rate limited by {{domain}} API — retrying"
          loggingLevel: WARN
```

---

## Required Config Properties

```properties
# application.properties
api.{{domain}}.url=${API_{{DOMAIN}}_URL}
```

---

## Error Scenarios

| Scenario | Retry? | Action |
|----------|--------|--------|
| 2xx | — | Continue |
| 4xx (not 429) | No | Log ERROR, route to DLQ |
| 429 | Yes (5x backoff) | Log WARN, retry |
| 5xx | Yes (3x backoff) | Log WARN, retry; then DLQ |
| Timeout | Yes (3x backoff) | Log WARN, retry; then DLQ |
