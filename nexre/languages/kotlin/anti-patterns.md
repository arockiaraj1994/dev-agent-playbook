---
title: Kotlin anti-patterns — NexRe
description: What NOT to do when writing Kotlin for NexRe.
language: kotlin
---

# Kotlin anti-patterns — NexRe

Know these before writing any code.

## Architecture anti-patterns

### Importing `data/` in `ui/`
The UI layer must only talk to `domain/` — use cases and repository interfaces.
Importing a `LinkRepositoryImpl`, `LinkDao`, or `OgFetcher` directly in a ViewModel or Composable breaks the layer contract and makes the code untestable.

```kotlin
// WRONG — ViewModel directly using data layer
class HomeViewModel @Inject constructor(private val linkDao: LinkDao) : ViewModel()

// RIGHT — ViewModel uses domain interface
class HomeViewModel @Inject constructor(private val linkRepository: LinkRepository) : ViewModel()
```

### Putting Android/framework code in `domain/`
`domain/model/` and `domain/usecase/` are pure Kotlin. No `Context`, `Intent`, `Room`, or `Retrofit` imports belong there. Use `@ApplicationContext` with Hilt only when unavoidable (e.g. `SummarizeLinkUseCase` needs context for `EncryptedSharedPreferences`).

### Business logic in Composables
No data fetching, repository calls, or coroutine launches in `@Composable` functions. All logic goes in the ViewModel.

---

## Compose anti-patterns

### `Row` for tags
Tags can be many and long. A plain `Row` clips or overflows vertically without wrapping.
```kotlin
// WRONG
Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
    tags.forEach { TagChip(label = it) }
}

// RIGHT
FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
    tags.forEach { TagChip(label = it) }
}
```

### Collecting Flow inside a Composable without `collectAsState`
```kotlin
// WRONG — creates new collector on every recomposition
val links = viewModel.links.value

// RIGHT
val links by viewModel.links.collectAsState()
```

### Using `LaunchedEffect` for navigation side-effects without a stable key
Use a unique, stable key (not `Unit`) for effects that should fire exactly once per event.

### Importing Material2 components
This project uses Material3 only. Never import from `androidx.compose.material` (M2) — always `androidx.compose.material3`.

---

## Room anti-patterns

### Changing a column name or table name without a migration
```kotlin
// WRONG — silently crashes on upgrade
@ColumnInfo(name = "img_url") val thumbnailUrl: String  // was "thumbnail_url"

// RIGHT — keep existing name OR add Migration object AND bump version
```

### Calling DAO methods on the main thread
All DAO methods in this project are either `suspend` or return `Flow`. Calling them from a non-coroutine context causes a `IllegalStateException`.

### Using `LiveData` instead of `Flow`
The project uses Kotlin `Flow` everywhere. Do not introduce `LiveData`.

### Storing business logic in a DAO query
DAOs contain SQL only — no Kotlin logic, no mapping, no filtering beyond what SQL can do.

---

## Coroutine anti-patterns

### `GlobalScope.launch`
Never use `GlobalScope`. Use `viewModelScope` in ViewModels, `lifecycleScope` in Activities, or `CoroutineScope(Dispatchers.IO)` in workers.

### Blocking calls on main dispatcher
```kotlin
// WRONG
fun fetchData() = runBlocking { ogFetcher.fetch(url) }

// RIGHT
fun fetchData() = viewModelScope.launch { ogFetcher.fetch(url) }
```

### `Thread.sleep` in coroutines
Use `delay()` inside coroutines, not `Thread.sleep()`.

---

## Security anti-patterns

### Storing the Gemini API key in `SharedPreferences`
The key MUST be stored in `EncryptedSharedPreferences`. Plain `SharedPreferences` is readable from a rooted device or backup.

### Logging the API key or link content
```kotlin
// WRONG
Log.d("NexRe", "api key = $apiKey")
Log.d("NexRe", "link content = ${link.summary}")
```

### Hardcoding the Gemini base URL as `http://`
The Retrofit base URL is `https://generativelanguage.googleapis.com` — never downgrade to HTTP.

---

## WorkManager anti-patterns

### Using synchronous `Worker` instead of `CoroutineWorker`
All workers in this project use `CoroutineWorker`. Synchronous `Worker` blocks the WorkManager thread pool.

### Unlimited retries
```kotlin
// WRONG — retries forever
return Result.retry()

// RIGHT — limit retries
return if (runAttemptCount < 2) Result.retry() else Result.failure()
```

### Constructing workers with `new` instead of Hilt
Workers must go through `NexReWorkerFactory` so Hilt can inject their dependencies.

---

## Dependency anti-patterns

### Hardcoding a version in `build.gradle.kts`
All versions belong in `gradle/libs.versions.toml`. Inline versions create version drift.

### Adding a library without checking if one already exists
Before adding Gson, check if Moshi is already handling JSON. Before adding a logging library, check if `android.util.Log` is sufficient.
