---
title: Java testing — Apache Camel
description: JUnit 5 + CamelTestSupport patterns for route and processor tests.
language: java
tags: [java, testing, junit, camel-test]
---

# Java testing — Apache Camel

## Frameworks

- **JUnit 5** for all tests.
- **`CamelTestSupport`** (camel-test-junit5) for route tests in plain Camel projects.
- **`@QuarkusTest`** when running on Quarkus (auto-starts the `CamelContext`).
- **WireMock** for stubbing REST upstreams. **`MockEndpoint`** for asserting messages reach an endpoint.
- **Testcontainers** for SFTP/JMS/Kafka brokers — never share a real shared broker between test runs.

## What every route test must cover

1. **Happy path** — message in, transformed message out at the expected endpoint.
2. **Error path** — induced failure (e.g. WireMock returns 500, or a processor throws) routes to the DLQ.
3. **Header propagation** — assert `routeId`, `CamelFileName`, or other headers used downstream survive the route.

## Patterns

- Wait for async completion with `NotifyBuilder` or `MockEndpoint.assertIsSatisfied(timeout)`. **Never `Thread.sleep`.**
- Mock only **external** endpoints. Don't `MockEndpoint` an internal bean — unit-test the bean directly.
- Assert message content, not just count. `mock.expectedBodiesReceived(...)` over `mock.expectedMessageCount(1)` alone.
- Use `AdviceWith` to swap real endpoints for mocks in route-under-test, not to rewrite route logic.

## Naming

- Test names describe the scenario: `shouldRouteToDlqWhenSftpAuthenticationFails`, `shouldRetryWith429Response`.

## Example skeleton

```java
class SftpInboundPaymentsRouteTest extends CamelTestSupport {
    @Override protected RouteBuilder createRouteBuilder() {
        return new RouteBuilder() {
            @Override public void configure() {
                AdviceWith.adviceWith(getContext(), "sftp-inbound-payments", a -> {
                    a.replaceFromWith("direct:test-in");
                    a.weaveByToUri("direct:transform-payments").replace().to("mock:transform");
                });
            }
        };
    }

    @Test
    void shouldRouteToTransformOnHappyPath() throws Exception {
        MockEndpoint mock = getMockEndpoint("mock:transform");
        mock.expectedMessageCount(1);
        mock.expectedBodiesReceived("payload");

        template.sendBody("direct:test-in", "payload");

        mock.assertIsSatisfied();
    }
}
```
