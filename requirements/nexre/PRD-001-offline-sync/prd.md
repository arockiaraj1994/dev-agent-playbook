---
id: PRD-001
title: Offline sync for saved articles
description: Let readers save articles and keep reading without a network.
status: approved
owner: raj
project: nexre
tags: [sync, offline, room]
---

# PRD-001 - Offline sync for saved articles

## Problem

NexRe readers often commute through tunnels and dead zones. Today, opening a
saved article without connectivity shows an empty shell and a retry spinner.
That breaks the core promise of a reading app: the article you saved should be
readable anywhere. Support tickets and store reviews repeatedly cite offline
reading as the top missing capability, and competitors already ship it.

## Goals

- Saved articles are fully readable with airplane mode on.
- Writes made offline (highlights, archive) sync when connectivity returns.
- Conflict UX is explicit when the same article was edited on two devices.

## Non-Goals

- Full catalog browsing while offline (only explicitly saved items).
- Background sync of the entire feed.
- Multi-user collaborative editing of a single article.

## Success Metrics

- ≥90% of saved-article opens succeed with no network within 30 days of ship.
- Offline write queue drains with <1% permanent failure rate.

## Open Questions

- None - conflict policy decided: last-write-wins with a visible banner.
