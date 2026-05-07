---
title: Kotlin standards — NexRe
description: Coding standards for Kotlin in NexRe (Android, Compose, Hilt, Room).
language: kotlin
---

# Kotlin standards — NexRe

## Language baseline

- Kotlin 2.1.0, JVM target 17.
- Use Kotlin idioms: `data class`, `sealed interface/class`, `when` expressions, extension functions.
- Prefer `val` over `var`. Use `var` only where mutability is required.
- Use `suspend` for all blocking operations. Never block the main thread.
- Coroutines: launch from `viewModelScope` in ViewModels, `withContext(Dispatchers.IO)` for I/O in use cases and repositories.

## Naming

| Thing | Convention | Example |
|-------|-----------|---------|
| Class / interface | PascalCase | `LinkRepositoryImpl` |
| Function | camelCase | `saveLink` |
| Composable | PascalCase | `DetailScreen` |
| Property / variable | camelCase | `linkId` |
| Constant | UPPER_SNAKE | `DEFAULT_MODEL_ID` |
| Package | lowercase, dot-separated | `com.mindshift.nexre.ui.home` |
| DB column name | snake_case via `@ColumnInfo` | `thumbnail_url` |
| Route string | lowercase-kebab or camelCase | `"detail/{linkId}"` |

## Project structure (must match existing)

```
app/src/main/java/com/mindshift/nexre/
  data/
    local/
      dao/          ← Room DAOs
      entity/       ← @Entity classes + relations
      NexReDatabase.kt
    remote/
      model/        ← Moshi DTOs
      GeminiApiService.kt
      OgFetcher.kt
      KeywordTagger.kt
    repository/     ← Repository implementations
  di/               ← Hilt modules
  domain/
    model/          ← Domain models (pure Kotlin)
    repository/     ← Repository interfaces
    usecase/        ← Use case classes
  share/            ← StoreActivity, SummarizeActivity
  ui/
    components/     ← Shared composables
    navigation/     ← NexReNavHost
    theme/          ← NexReTheme, Color, Type
    <feature>/      ← <Feature>Screen.kt + <Feature>ViewModel.kt
  worker/           ← WorkManager workers
  MainActivity.kt
  MainViewModel.kt
  NexReApplication.kt
```

## Dependency management

- All versions in `gradle/libs.versions.toml`. Never hardcode a version in `build.gradle.kts`.
- Add new libraries as `[libraries]` entries first, then reference with `libs.<name>`.
- KSP is used for Hilt, Room, and Moshi codegen — annotated classes must be in the main source set.

## Compose conventions

- Stateful screens: `@Composable fun <Name>Screen(viewModel: <Name>ViewModel = hiltViewModel())`.
- Stateless sub-composables: `@Composable private fun <Name>(...)` in the same file.
- Collect StateFlow with `val x by viewModel.x.collectAsState()`.
- Use `Arrangement.spacedBy()` for spacing instead of manual `Spacer` in lists/rows.
- Use `FlowRow` (not `Row`) for any chip/tag collection that may overflow.
- Material3 only — do not use Material2 or accompanist for anything already in M3.
- Opt-ins at function level: `@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)`.
- Global opt-ins are already enabled in `build.gradle.kts` for `ExperimentalMaterial3Api`, `ExperimentalFoundationApi`, and `ExperimentalLayoutApi`.

## StateFlow / UiState patterns

- ViewModels expose state as `StateFlow<T>` started with `SharingStarted.WhileSubscribed(5000)`.
- One-shot events (snackbars, navigation) use a nullable `StateFlow<Event?>` consumed with `consumeEvent()`.
- Sealed classes/interfaces for complex UI states: `Loading`, `Success(data)`, `Error`.

## Hilt rules

- `@HiltViewModel` on every ViewModel — use `hiltViewModel()` in composables.
- `@Singleton` on repository implementations and remote service classes.
- `@HiltWorker` + `@AssistedInject` on WorkManager workers.
- Hilt modules in `di/` — one module per concern (Database, Network, Repository, Worker).

## Room rules

- DAOs return `Flow<List<T>>` for observable queries and `suspend` for mutations.
- Use `@Upsert` for insert-or-replace patterns.
- Partial updates use dedicated `@Query` with `@Update` or targeted SQL.
- Never call DAO methods on the main thread — they are `suspend` or `Flow`-based.

## Error handling

- Use `runCatching { ... }.getOrDefault(fallback)` for non-critical parse/enum lookups.
- Use `try { ... } catch (e: Exception)` for network calls in use cases — map to domain result types.
- Never `catch (e: Throwable)` silently — always log or map to an error state.
- WorkManager: return `Result.retry()` for transient failures, `Result.failure()` for permanent ones.
