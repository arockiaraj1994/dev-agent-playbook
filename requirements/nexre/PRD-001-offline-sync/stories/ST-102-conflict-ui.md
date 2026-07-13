---
id: ST-102
title: Show conflict banner on divergent edits
description: Surface last-write-wins conflicts to the reader.
status: approved
priority: P1
targets: [pattern:compose-screen, pattern:viewmodel, language:kotlin/testing]
depends_on: [ST-101]
---

# ST-102 - Show conflict banner on divergent edits

## User Story

As a multi-device reader, I want to know when my offline edit lost a conflict,
so that I can re-apply a highlight that was overwritten.

## Requirements

- Detect server version newer than the queued write.
- Show a non-blocking banner on the article screen.
- Offer a one-tap "re-apply my change" action.

## Acceptance Criteria

- [ ] Given a queued highlight and a newer server revision, When sync runs, Then a conflict banner appears.
- [ ] Given the banner is visible, When the reader taps re-apply, Then a new mutation is enqueued.
- [ ] Given no conflict, When sync succeeds, Then no banner is shown.
