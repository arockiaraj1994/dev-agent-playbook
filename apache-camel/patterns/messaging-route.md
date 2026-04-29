---
title: Messaging route pattern — Apache Camel
description: Canonical pattern for consuming and producing messages via JMS (ActiveMQ, IBM MQ) or Kafka with DLQ wiring.
type: pattern
tags: [camel, jms, kafka, messaging, integration]
see_also: [pattern:error-handling, skill:add-route]
---

# Pattern: Messaging Route

Standard pattern for consuming and producing messages via JMS (ActiveMQ, IBM MQ) or Kafka.

---

## Rules

- Always set `routeId`.
- Use `concurrentConsumers` to control parallelism — default of 1 is rarely right for production.
- Always define a DLQ route; for JMS use the broker's native DLQ or `deadLetterQueue` option.
- Never decode or log full message body if it may contain PII.
- For Kafka: set `groupId`, `autoOffsetReset`, and `autoCommitEnable` deliberately.

---

## JMS Consumer Route

```yaml
- errorHandler:
    deadLetterChannel:
      deadLetterUri: "jms:queue:{{jms.dlq.queue}}"
      maximumRedeliveries: 3
      redeliveryDelay: 2000
      useExponentialBackOff: true

- route:
    id: jms-consumer-{{domain}}
    from:
      uri: "jms:queue:{{jms.inbound.queue}}"
      parameters:
        concurrentConsumers: 5
        maxConcurrentConsumers: 20
        transacted: true
    steps:
      - log:
          message: "Received JMS message: ${header.JMSMessageID}"
          loggingLevel: INFO
      - to:
          uri: "direct:process-{{domain}}"
```

## JMS Producer Route

```yaml
- route:
    id: jms-producer-{{domain}}
    from:
      uri: "direct:publish-{{domain}}"
    steps:
      - setHeader:
          name: "JMSCorrelationID"
          simple: "${header.correlationId}"
      - to:
          uri: "jms:queue:{{jms.outbound.queue}}"
      - log:
          message: "Published to {{jms.outbound.queue}}: ${header.JMSMessageID}"
          loggingLevel: INFO
```

---

## Kafka Consumer Route

```yaml
- route:
    id: kafka-consumer-{{domain}}
    from:
      uri: "kafka:{{kafka.topic.inbound}}"
      parameters:
        brokers: "{{kafka.brokers}}"
        groupId: "{{kafka.group.id}}"
        autoOffsetReset: "earliest"
        autoCommitEnable: false
        allowManualCommit: true
        maxPollRecords: 100
    steps:
      - log:
          message: "Kafka message: topic=${header.kafka.TOPIC} partition=${header.kafka.PARTITION} offset=${header.kafka.OFFSET}"
          loggingLevel: INFO
      - to:
          uri: "direct:process-{{domain}}"
      - bean:
          ref: kafkaManualCommit
          method: commitSync
```

## Kafka Producer Route

```yaml
- route:
    id: kafka-producer-{{domain}}
    from:
      uri: "direct:publish-{{domain}}"
    steps:
      - setHeader:
          name: "kafka.KEY"
          simple: "${header.messageKey}"
      - to:
          uri: "kafka:{{kafka.topic.outbound}}"
          parameters:
            brokers: "{{kafka.brokers}}"
      - log:
          message: "Published to {{kafka.topic.outbound}}"
          loggingLevel: INFO
```

---

## Required Config Properties

```properties
# JMS
jms.inbound.queue=${JMS_INBOUND_QUEUE}
jms.outbound.queue=${JMS_OUTBOUND_QUEUE}
jms.dlq.queue=${JMS_DLQ_QUEUE}

# Kafka
kafka.brokers=${KAFKA_BROKERS}
kafka.topic.inbound=${KAFKA_TOPIC_INBOUND}
kafka.topic.outbound=${KAFKA_TOPIC_OUTBOUND}
kafka.group.id=${KAFKA_GROUP_ID}
```

---

## Error Scenarios

| Scenario | JMS | Kafka |
|----------|-----|-------|
| Processing failure | Rollback (transacted=true), retry, then broker DLQ | Do not commit offset, retry via error handler |
| Poison message | After max retries → DLQ queue | After max retries → DLQ topic or log |
| Broker unavailable | Camel reconnects automatically (JMS) | Kafka client retries with backoff |
