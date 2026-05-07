---
title: Compose screen pattern — NexRe
description: How Compose screens are structured in NexRe (Scaffold, TopAppBar, StateFlow, Hilt).
tags: [compose, material3, screen, hilt, kotlin]
see_also: [pattern:viewmodel, skill:add-screen]
---

# Pattern: Compose screen — NexRe

**Use this when:** adding a new screen or a major new UI surface.

## File layout

```
ui/<feature>/
  <Feature>Screen.kt    ← @Composable, uses hiltViewModel()
  <Feature>ViewModel.kt ← @HiltViewModel
```

Route is defined in `ui/navigation/NexReNavHost.kt`.

## Canonical example — screen with TopAppBar

```kotlin
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun DetailScreen(
    onBack: () -> Unit,
    viewModel: DetailViewModel = hiltViewModel(),
) {
    val link by viewModel.link.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = {},
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Outlined.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
    ) { padding ->
        link?.let { l ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(l.title, style = MaterialTheme.typography.headlineSmall)
                // ... content
                if (l.tags.isNotEmpty()) {
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        l.tags.forEach { tag -> TagChip(label = tag) }
                    }
                }
            }
        }
    }
}
```

## Canonical example — screen with bottom nav (no TopAppBar)

Bottom-nav screens (Home, Library, Topics, Settings) don't include a TopAppBar — the Scaffold in `NexReNavHost` handles the bottom bar, and the screen owns only its content.

```kotlin
@Composable
fun HomeScreen(
    onLinkClick: (Link) -> Unit,
    onSearchClick: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val links by viewModel.links.collectAsState()
    // Content only — no Scaffold, no TopAppBar
    Column(modifier = Modifier.fillMaxSize()) { /* ... */ }
}
```

## Adding the route

In `NexReNavHost.kt`:
```kotlin
composable("my-feature") {
    MyFeatureScreen(onBack = { navController.popBackStack() })
}
```

If the route appears in the bottom nav, add it to `bottomNavItems`.

## Key rules

- `hiltViewModel()` — never construct ViewModels manually.
- `collectAsState()` — always collect `StateFlow` this way; not `.value`.
- `FlowRow` — use it for any tag/chip row, not `Row`.
- Material3 only — `TopAppBar`, `Scaffold`, `Card`, `Button` all from `androidx.compose.material3`.
- Private sub-composables in the same file: `@Composable private fun SomePart(...)`.
- Typography: `MaterialTheme.typography.headlineSmall`, `.titleMedium`, `.bodyLarge`, `.labelSmall` — match what other screens use.
- Colors: always via `MaterialTheme.colorScheme.*` — no hardcoded colors.
- Navigation callbacks passed as lambdas (`onBack: () -> Unit`, `onLinkClick: (Link) -> Unit`) — screens are navigation-agnostic.
