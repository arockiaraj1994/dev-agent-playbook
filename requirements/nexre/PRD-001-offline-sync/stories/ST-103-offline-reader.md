---
id: ST-103
title: Render saved article body offline
description: Open a saved article with no network and see full content.
status: draft
priority: P0
targets: [pattern:repository, pattern:usecase, skill:add-screen]
depends_on: []
---

# ST-103 - Render saved article body offline

## User Story

As a reader underground, I want to open a saved article with no signal,
so that my commute reading is uninterrupted.

## Requirements

- Article body HTML/Markdown is cached at save time.
- Reader screen loads exclusively from local storage when offline.
- Missing cache shows a clear empty state (not a spinner forever).

## Acceptance Criteria

- [ ] Saving an article stores body bytes in Room/filesystem.
- [ ] Opening it in airplane mode renders the full article.
- [ ] If cache is missing, the UI explains how to re-save while online.
