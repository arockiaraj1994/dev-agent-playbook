---
title: Definition of Done — NexRe
description: Build + lint + security gates that must pass before a task is complete.
---

# Definition of Done — NexRe

## Mechanical (run via `gates/scripts/verify-kotlin.sh`)

- [ ] `./gradlew assembleDebug` — debug build compiles with zero errors
- [ ] `./gradlew assembleRelease` — release build with R8/minification compiles clean
- [ ] `./gradlew lint` — zero new lint errors or warnings introduced
- [ ] `./gradlew test` — all unit tests pass (if any exist for the changed code)

## Schema changes (if a Room entity was modified)

- [ ] `NexReDatabase.version` is incremented
- [ ] A `Migration` object is defined and added to `addMigrations(...)` in `DatabaseModule`
- [ ] The migration is tested manually on a device/emulator with existing data

## Functional

- [ ] The feature works end-to-end on a physical device or emulator (API 26+)
- [ ] Share-sheet flows (StoreActivity + SummarizeActivity) still work after the change
- [ ] Navigation — back stack and bottom-nav transitions are correct
- [ ] No visible regressions in Home, Library, Topics, Settings, Detail, Search screens
- [ ] Tags display correctly in `FlowRow` (no vertical overflow)
- [ ] Gemini summary + tagging path still works (if Gemini-related code was changed)
- [ ] Keyword tagger fallback still works when no API key is set

## Security

- [ ] No new hardcoded secrets, tokens, or API keys in source
- [ ] Gemini API key is accessed only via `EncryptedSharedPreferences` in the use case layer
- [ ] No user data (link content, notes, summaries) appears in logcat
- [ ] No new network endpoints added beyond Gemini and OG fetch
- [ ] ProGuard rules updated if new reflection-used classes were added (Moshi adapters, etc.)

## Privacy

- [ ] No new analytics, crash reporting, or telemetry code introduced
- [ ] Export (JSON) goes to local Downloads via `FileProvider`, not any cloud
- [ ] No user data sent to external services without explicit user action
