---
title: Add use case — NexRe
description: Playbook for adding a new use case in the domain layer.
triggers: [add use case, new use case, add business logic, new operation]
see_also: [pattern:usecase, pattern:repository, language:kotlin/standards]
---

# Skill: Add use case — NexRe

## Steps

1. **Create the file** — `domain/usecase/<Name>UseCase.kt`
   - Class name: `<Name>UseCase` (verb-noun, e.g. `ExportJsonUseCase`, `ValidateGeminiKeyUseCase`).
   - `@Inject constructor(...)` — no `@Singleton`; use cases are not cached.

2. **Define dependencies** — inject repository interfaces and remote services.
   - Only inject interfaces from `domain/repository/` or classes from `data/remote/` that have no Android dependencies.
   - If you need `Context`, use `@ApplicationContext` via Hilt (acceptable for `EncryptedSharedPreferences`). Flag this in a comment.

3. **Define the entry point**
   - Single operation: `suspend operator fun invoke(param: Type): ReturnType`
   - Multiple operations (related): named `suspend fun invokeX(...)` methods.

4. **Define a sealed result type** if the operation has domain-meaningful failure modes:
   ```kotlin
   sealed interface Result {
       data class Success(val data: T) : Result
       data object NoApiKey : Result
       data object NoInternet : Result
   }
   ```
   - Catch all exceptions inside the use case. Map network exceptions to result types — never let raw exceptions propagate to the ViewModel.

5. **Return domain types** — `Link`, `List<Tag>`, etc. Never return `LinkEntity`, Room, or Retrofit types.

6. **Inject into the ViewModel** — add the use case to the ViewModel's constructor and call it from `viewModelScope.launch { ... }`.

7. **Build** — `./gradlew assembleDebug`. Hilt will fail at compile time if the dependency graph is broken.

## Constraints

- No Android imports except `@ApplicationContext` with explicit justification.
- No Compose imports.
- No direct DAO usage — only repository interfaces.
- Use cases are not `@Singleton` — they are instantiated per-injection (lightweight).
- Don't put UI logic (snackbar messages, navigation) in the use case — those belong in the ViewModel.
