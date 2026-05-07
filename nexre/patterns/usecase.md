---
title: Use case pattern — NexRe
description: How use cases are structured and named in NexRe.
tags: [usecase, domain, kotlin, clean-architecture]
see_also: [pattern:repository, skill:add-usecase]
---

# Pattern: Use case — NexRe

**Use this when:** adding a new business operation that involves multiple data sources, or encapsulating logic that shouldn't live in a ViewModel or repository.

## Structure

```
domain/usecase/<Name>UseCase.kt
```

Use cases live in `domain/usecase/`. They are plain Kotlin classes — no Android imports except `@ApplicationContext` when strictly required (e.g., for `EncryptedSharedPreferences`).

## Simple use case (single result)

```kotlin
class SaveLinkUseCase @Inject constructor(
    private val ogFetcher: OgFetcher,
    private val keywordTagger: KeywordTagger,
    private val linkRepository: LinkRepository,
) {
    suspend operator fun invoke(url: String): Link {
        val og = ogFetcher.fetch(url)
        val tags = keywordTagger.tag(og.title, og.description)
        val link = Link(
            id = UUID.randomUUID().toString(),
            url = url,
            // ... map og fields
            savedAt = Instant.now().toEpochMilli(),
        )
        linkRepository.saveLink(link, "KEYWORD")
        return link
    }
}
```

## Use case with sealed result type

Use a sealed result type when the operation can fail in domain-meaningful ways:

```kotlin
class SummarizeLinkUseCase @Inject constructor(/* ... */) {

    sealed interface Result {
        data class Success(val link: Link) : Result
        data object NoApiKey : Result
        data object NoInternet : Result
        data class GeminiError(val message: String) : Result
    }

    suspend operator fun invoke(url: String): Result {
        val apiKey = getApiKey() ?: return Result.NoApiKey
        // ... call Gemini, save link
        return Result.Success(link)
    }
}
```

## Key rules

- Use cases are `@Inject constructor` — Hilt provides all dependencies.
- Single public entry point: prefer `operator fun invoke(...)` for single-operation use cases.
- Multiple named operations are fine for related concerns (e.g., `invokeText` vs `invoke` in `SummarizeLinkUseCase`).
- Return domain types (`Link`, `List<Tag>`) or sealed results — never entity classes or DTOs.
- Network errors are caught inside the use case and mapped to a sealed result — never let raw exceptions propagate to the ViewModel.
- No Compose, no ViewModel, no `@HiltViewModel` — use cases are plain Kotlin with `@Inject`.
- `@ApplicationContext` is acceptable when the use case needs `EncryptedSharedPreferences` (e.g., reading the Gemini API key). Avoid it otherwise.
