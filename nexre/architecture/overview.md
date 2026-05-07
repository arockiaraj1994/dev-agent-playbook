---
title: Architecture — NexRe
description: Layer map, module boundaries, data flow, and tech stack for NexRe.
---

# Architecture — NexRe

## System overview

NexRe is a **single-module Android app** with no backend. All user data is stored on-device in a Room SQLite database. The only outbound network calls are:
1. **OG metadata fetch** — Jsoup-based HTTP GET of the user's URL to extract title/description/image.
2. **Gemini API** — HTTPS POST to `generativelanguage.googleapis.com` for AI summaries (opt-in, requires user API key).

The app follows **Clean Architecture** with three layers.

---

## Layer map

```
ui/           ← Jetpack Compose screens + HiltViewModels
  ↓ (calls use cases / repository interface)
domain/       ← Use cases, repository interfaces, domain models (pure Kotlin)
  ↓ (implemented by)
data/         ← Room DAOs, Retrofit services, OgFetcher, KeywordTagger, repository impls
```

### `ui/` — Presentation layer

| Package | Contents |
|---------|----------|
| `ui/navigation/` | `NexReNavHost` — bottom nav + NavHost, all route definitions |
| `ui/home/` | `HomeScreen`, `HomeViewModel` |
| `ui/library/` | `LibraryScreen`, `LibraryViewModel` |
| `ui/detail/` | `DetailScreen`, `DetailViewModel` |
| `ui/search/` | `SearchScreen`, `SearchViewModel` |
| `ui/tags/` | `TagsScreen`, `TagsViewModel` |
| `ui/settings/` | `SettingsScreen`, `SettingsViewModel` |
| `ui/share/` | `SummarizeBottomSheetRoot`, `ShareViewModel` |
| `ui/onboarding/` | `OnboardingScreen` |
| `ui/components/` | Shared composables: `TagChip`, `LinkCard`, `GradientThumbnail`, `SourceBadge`, `ReadDot`, `EmptyState` |
| `ui/theme/` | `NexReTheme`, `Color`, `Type` |

### `domain/` — Business logic layer

| Package | Contents |
|---------|----------|
| `domain/model/` | `Link`, `Tag`, `LinkStatus`, `SourcePlatform`, `SummarySource` |
| `domain/repository/` | `LinkRepository`, `TagRepository` interfaces |
| `domain/usecase/` | `SaveLinkUseCase`, `SaveTextUseCase`, `SummarizeLinkUseCase`, `ValidateGeminiKeyUseCase`, `ExportJsonUseCase` |

### `data/` — Data layer

| Package | Contents |
|---------|----------|
| `data/local/` | `NexReDatabase`, `LinkDao`, `TagDao` |
| `data/local/entity/` | `LinkEntity`, `TagEntity`, `LinkTagCrossRef`, `LinkWithTags` |
| `data/remote/` | `GeminiApiService`, `OgFetcher`, `KeywordTagger` |
| `data/remote/model/` | Moshi-annotated Gemini request/response DTOs |
| `data/repository/` | `LinkRepositoryImpl`, `TagRepositoryImpl` |

### Entry points

| Class | Purpose |
|-------|---------|
| `MainActivity` | Main app entry point — hosts `NexReNavHost` |
| `share/StoreActivity` | Share target for silent save (no Gemini) |
| `share/SummarizeActivity` | Share target for AI-powered save with bottom sheet |
| `NexReApplication` | `@HiltAndroidApp`, WorkManager initialization |

### DI modules (`di/`)

| Module | Provides |
|--------|---------|
| `DatabaseModule` | `NexReDatabase`, `LinkDao`, `TagDao` |
| `NetworkModule` | OkHttp client, Retrofit, `GeminiApiService`, Moshi |
| `RepositoryModule` | `LinkRepository` → `LinkRepositoryImpl`, `TagRepository` → `TagRepositoryImpl` |
| `WorkerModule` | `NexReWorkerFactory` — custom WorkManager factory for `@HiltWorker` |

### Workers (`worker/`)

| Worker | Trigger | Purpose |
|--------|---------|---------|
| `StoreLinkWorker` | Enqueued by `StoreActivity` | OG fetch + keyword tag + Room save (background) |
| `WeeklyDigestWorker` | Periodic (weekly) | Sends a notification summarising saved-this-week count |
| `DailyReminderWorker` | Periodic (daily) | Nudges user to read unread links |

---

## Data flow: Save via share sheet (silent)

```
User shares URL
  → StoreActivity.onCreate()
  → enqueue StoreLinkWorker(url)
  → StoreLinkWorker.doWork()
  → SaveLinkUseCase(url)
      → OgFetcher.fetch(url)          [network: OG metadata]
      → KeywordTagger.tag(title, desc)
      → LinkRepository.saveLink(link)
          → LinkDao.upsertLink()       [Room write]
          → TagDao.insertTag() × N
          → LinkDao.upsertLinkTagCrossRefs()
  → showSaveNotification()
```

## Data flow: Save via share sheet (Gemini)

```
User shares URL with "Summarize & Save NexRe"
  → SummarizeActivity.onCreate()
  → ShareViewModel.startSummarize(url)
  → SummarizeLinkUseCase(url)
      → OgFetcher.fetch(url)
      → GeminiApiService.generateContent()  [network: Gemini API]
      → parse JSON → summary + geminiTags
      → KeywordTagger.tag() for fallback tags
      → LinkRepository.saveLink(link)
  → SummarizeBottomSheetRoot shows summary
  → User taps "Save" → viewModel.confirmSave() → Result.Success path exits
```

---

## Database schema

### `links` table (`LinkEntity`)
| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID |
| `url` | TEXT | |
| `title` | TEXT | |
| `description` | TEXT | OG description |
| `thumbnail_url` | TEXT | OG image |
| `source_platform` | TEXT | `SourcePlatform.name` |
| `status` | TEXT | `LinkStatus.name` |
| `is_favourite` | INTEGER | Boolean |
| `personal_note` | TEXT | |
| `summary` | TEXT | Gemini or OG |
| `summary_source` | TEXT | `SummarySource.name` |
| `saved_at` | INTEGER | epoch ms |
| `opened_at` | INTEGER | epoch ms |
| `read_duration_sec` | INTEGER | |
| `read_count` | INTEGER | |

### `tags` table (`TagEntity`)
| Column | Type |
|--------|------|
| `id` | INTEGER PK (autoGenerate) |
| `name` | TEXT |

### `link_tags` join table (`LinkTagCrossRef`)
| Column | Type | Notes |
|--------|------|-------|
| `link_id` | TEXT FK | |
| `tag_id` | INTEGER FK | |
| `source` | TEXT | `"KEYWORD"` or `"GEMINI"` |

---

## Navigation routes

```
home
library
library?tag={tag}
tags
settings
search
detail/{linkId}
```

Defined in `NexReNavHost`. Bottom nav shows for: `home`, `library`, `tags`, `settings`.
