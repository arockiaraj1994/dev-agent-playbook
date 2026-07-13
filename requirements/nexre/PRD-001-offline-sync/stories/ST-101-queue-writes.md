---
id: ST-101
title: Queue writes while offline
description: Persist offline mutations and replay them when online.
status: approved
priority: P0
targets: [pattern:repository, skill:add-room-column, language:kotlin/testing]
depends_on: []
---

# ST-101 - Queue writes while offline

## User Story

As a commuter reader, I want my highlights and archive actions to succeed
while offline, so that I do not lose work when the train loses signal.

## Requirements

- Local Room table stores pending mutations with idempotency keys.
- A sync worker drains the queue when connectivity returns.
- Failures retry with backoff; permanent failures surface in UI.

## Acceptance Criteria

- [ ] Creating a highlight with airplane mode on persists locally and shows as pending.
- [ ] Restoring connectivity drains the queue and clears the pending badge.
- [ ] A forced 500 from the API leaves the item retryable, not dropped.
