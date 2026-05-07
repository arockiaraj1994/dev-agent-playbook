---
title: ViewModel pattern — NexRe
description: How ViewModels expose state and handle events in NexRe.
tags: [viewmodel, stateflow, compose, hilt, kotlin]
see_also: [pattern:usecase, pattern:compose-screen]
---

# Pattern: ViewModel — NexRe

**Use this when:** adding or modifying a ViewModel for a Compose screen.

## Structure

```
ui/<feature>/
  <Feature>Screen.kt    ← @Composable screen
  <Feature>ViewModel.kt ← @HiltViewModel
```

## Canonical example — simple state (list)

```kotlin
@HiltViewModel
class HomeViewModel @Inject constructor(
    private val linkRepository: LinkRepository,
) : ViewModel() {

    val links = linkRepository.getHomeLinks()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun archive(link: Link) = viewModelScope.launch {
        linkRepository.updateStatus(link.id, LinkStatus.ARCHIVED)
    }
}
```

## Canonical example — one-shot events (snackbar / export)

```kotlin
@HiltViewModel
class SettingsViewModel @Inject constructor(/* ... */) : ViewModel() {

    private val _event = MutableStateFlow<SettingsEvent?>(null)
    val event: StateFlow<SettingsEvent?> = _event.asStateFlow()

    fun exportData() = viewModelScope.launch {
        val result = exportJsonUseCase()
        _event.value = when (result) {
            is ExportJsonUseCase.Result.Success -> SettingsEvent.ExportDone(result.fileName)
            is ExportJsonUseCase.Result.Error -> SettingsEvent.ExportError
        }
    }

    fun consumeEvent() { _event.value = null }
}

sealed interface SettingsEvent {
    data class ExportDone(val fileName: String) : SettingsEvent
    data object ExportError : SettingsEvent
}
```

## Consuming events in a Composable

```kotlin
val event by viewModel.event.collectAsState()

LaunchedEffect(event) {
    when (val e = event) {
        is SettingsEvent.ExportDone -> snackbarHostState.showSnackbar("Exported: ${e.fileName}")
        null -> {}
    }
    if (event != null) viewModel.consumeEvent()
}
```

## Key rules

- `@HiltViewModel` annotation is required — use `hiltViewModel()` in the Composable, never construct manually.
- `viewModelScope.launch` for fire-and-forget mutations.
- `SharingStarted.WhileSubscribed(5000)` for `stateIn` — the 5-second grace prevents restart on config change.
- One-shot events use a nullable `StateFlow<Event?>` — consuming sets it back to `null`.
- Never collect `Flow` inside a ViewModel with `collect {}` directly — use `stateIn` or `launchIn`.
- No Android framework classes in the ViewModel constructor beyond `@ApplicationContext` when strictly needed.
- No direct DAO imports — only repository interfaces and use cases.
