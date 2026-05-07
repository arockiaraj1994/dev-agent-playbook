---
title: Add screen — NexRe
description: Playbook for adding a new Compose screen with ViewModel, state, and navigation route.
triggers: [add screen, new screen, add page, new page, create screen]
see_also: [pattern:compose-screen, pattern:viewmodel, language:kotlin/standards]
---

# Skill: Add screen — NexRe

## Steps

1. **Create the ViewModel** — `ui/<feature>/<Feature>ViewModel.kt`
   - Annotate `@HiltViewModel`.
   - Inject repository interfaces or use cases — never DAOs directly.
   - Expose state as `StateFlow` with `stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), initial)`.
   - One-shot events (snackbar, navigate-away) use a nullable `StateFlow<Event?>` + `consumeEvent()`.

2. **Create the screen composable** — `ui/<feature>/<Feature>Screen.kt`
   - Top-level function: `@Composable fun <Feature>Screen(onBack: () -> Unit, ..., viewModel: <Feature>ViewModel = hiltViewModel())`.
   - Use `Scaffold` with `TopAppBar` if this is a pushed screen (not a bottom-nav root).
   - Collect state with `val x by viewModel.x.collectAsState()`.
   - Use `FlowRow` for any tag/chip collection.
   - Keep private sub-composables in the same file.
   - Add `@OptIn(ExperimentalMaterial3Api::class)` if using TopAppBar or other experimental M3 APIs.

3. **Register the route** — `ui/navigation/NexReNavHost.kt`
   - Add a `composable("my-feature") { ... }` entry inside `NavHost`.
   - If the screen takes arguments: `composable("detail/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType }))`.
   - If it should appear in the bottom nav, add a `NavItem` to `bottomNavItems`.

4. **Wire up navigation** — add click handlers in the calling screen to `navController.navigate("my-feature")`.

5. **Build** — run `./gradlew assembleDebug`. Fix any Hilt or Compose compilation errors.

6. **Verify manually** — open the screen, check state loading, back navigation, edge cases (empty state, error).

## Constraints

- Don't add a new library for anything Material3 already provides.
- Screen composables must not import from `data/` — only `domain/` models and `ui/components/`.
- Route strings are simple lowercase paths. Never use spaces or special characters.
- If the screen needs a tag/chip row, always use `FlowRow` — never `Row`.
- All navigation callbacks are lambdas — screens don't hold a reference to `NavController`.
