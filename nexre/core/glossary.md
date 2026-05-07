---
title: Glossary — NexRe
description: Domain terms used in NexRe. Use these exact words in code, comments, and discussion.
---

# Glossary — NexRe

| Term | Meaning |
|------|---------|
| **Link** | The central domain object. Represents a saved URL or plain-text note. Defined in `domain/model/Link.kt`. |
| **Tag** | A short topic label attached to a Link (e.g. "Android", "AI"). Tags are stored as a separate `tags` table with a many-to-many join via `link_tags`. |
| **LinkStatus** | Enum: `UNREAD`, `READ`, `ARCHIVED`. Controls which links appear in Home vs. Library. |
| **SourcePlatform** | Enum: `GITHUB`, `LINKEDIN`, `TWITTER`, `MEDIUM`, `DEV`, `STACKOVERFLOW`, `RESEARCH`, `WEB`, `TEXT`. Detected from the URL domain. `TEXT` means a plain-text note. |
| **SummarySource** | Enum: `NONE`, `OG_META`, `GEMINI`. Tracks whether the summary came from OG metadata or Gemini. |
| **OG fetch** | Fetching Open Graph metadata (title, description, image, body text) from a URL using Jsoup. Done in `OgFetcher`. |
| **Gemini summary** | An AI-generated 4–6-bullet summary produced by calling the Gemini REST API. Stored in `Link.summary` with `SummarySource.GEMINI`. |
| **Keyword tagger** | Rule-based tag assignment in `KeywordTagger` — scans title + description for known keywords and assigns topic tags. Runs as a fallback when Gemini is unavailable. |
| **Store (silent save)** | Saving a link without Gemini — via `StoreActivity` + `StoreLinkWorker` + `SaveLinkUseCase`. Uses OG fetch + keyword tagger only. |
| **Summarize** | Saving a link with Gemini — via `SummarizeActivity` + `SummarizeLinkUseCase`. Shows a bottom sheet with the AI summary before saving. |
| **Home** | The main feed screen. Shows UNREAD links sorted by `savedAt` desc. Routes: `home`. |
| **Library** | The filtered-by-status screen. Shows READ, ARCHIVED, FAVOURITES, or all links. Routes: `library`, `library?tag=<tag>`. |
| **Topics** | The tag browser screen (`TagsScreen`). Lists all tags with link counts. Route: `tags`. |
| **Detail** | The per-link detail screen (`DetailScreen`). Shows summary, tags, personal note, stats. Route: `detail/{linkId}`. |
| **Search** | Full-text search screen over link titles and descriptions. Route: `search`. |
| **Personal note** | Free-text annotation added by the user in the Detail screen. Stored in `Link.personalNote`. |
| **LinkWithTags** | Room relation object combining `LinkEntity` with its associated `TagEntity` list. Used in all DAO return types. |
| **WorkManager** | Background processing framework used for StoreLinkWorker (save), WeeklyDigestWorker (notifications), DailyReminderWorker. |
| **EncryptedSharedPreferences** | Android Jetpack library used to store the Gemini API key securely. The master key uses AES256-GCM. |
| **FileProvider** | Android content-provider used for the JSON export feature — serves the export file to the system download manager without exposing file paths. |
| **NexReDatabase** | The single Room database class. Located at `data/local/NexReDatabase.kt`. |
