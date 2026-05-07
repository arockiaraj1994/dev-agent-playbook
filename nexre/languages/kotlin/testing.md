---
title: Kotlin testing — NexRe
description: Testing approach for NexRe. Unit tests for use cases and ViewModels; no instrumentation tests yet.
language: kotlin
---

# Kotlin testing — NexRe

## Current state

NexRe is a single-developer project in early release. There are **no automated tests yet**. The priority is to add them incrementally as new features are added. When you write a use case or ViewModel, add a matching test file.

## Where tests live

```
app/src/test/java/com/mindshift/nexre/   ← unit tests (JVM)
app/src/androidTest/java/...            ← instrumented tests (device/emulator)
```

## What to test

### Use cases (highest priority)
- Each use case gets a `<Name>UseCaseTest.kt` in `src/test/`.
- Mock the repository interface with Mockito or a hand-written fake.
- Test: happy path, fallback/error path, edge cases (empty input, null OG data).

### ViewModels
- Use `kotlinx-coroutines-test` and `TestCoroutineScheduler`.
- Replace `SharingStarted.WhileSubscribed(5000)` with `SharingStarted.Eagerly` in tests or use `runTest`.
- Test state transitions: initial state, after load, after user action.

### Repository implementations
- Use an in-memory Room database (`Room.inMemoryDatabaseBuilder()`).
- Test that `saveLink` writes the link and cross-refs correctly.
- Test `searchLinks` returns the right results.

### Composables
- Not required yet. If you add Compose UI tests, use `ComposeTestRule` and test user-visible behavior, not implementation details.

## Rules

- Test names describe the scenario: `shouldReturnNoApiKeyWhenKeyIsBlank`.
- Prefer fakes over mocks for repositories — they are simpler and don't break on refactors.
- Never `Thread.sleep()` in tests — use `runTest` and `advanceUntilIdle()`.
- Don't test Room internals (SQL) — test through the repository interface.
- Each test class tests one class. Don't combine multiple features in one test file.
