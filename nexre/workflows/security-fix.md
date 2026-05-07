---
title: Workflow — Security fix
description: Flow for addressing security vulnerabilities in NexRe.
triggers: [security fix, vulnerability, CVE, secret leak, privacy issue, api key exposed]
gates: [verify-kotlin]
see_also: [core:guardrails, language:kotlin/anti-patterns]
---

# Workflow — Security fix (NexRe)

## Before you start

1. Understand the severity and scope — does this affect user data, credentials, or network security?
2. Read `core/guardrails.md` — security and privacy rules are non-negotiable.

## Common security issues and fixes

### API key exposed in logs or plaintext storage
- The Gemini API key MUST be stored in `EncryptedSharedPreferences` with `MasterKey.KeyScheme.AES256_GCM`.
- Key is read only in `SummarizeLinkUseCase.getApiKey()` — nowhere else.
- If key appears in `android.util.Log.*` calls, remove them immediately.
- Never store the key in `SharedPreferences`, `DataStore`, or any plaintext file.

### Dependency with a CVE
1. Identify the vulnerable library in `gradle/libs.versions.toml`.
2. Update the `[versions]` entry to the patched version.
3. Run `./gradlew assembleDebug` and `./gradlew assembleRelease` — verify the build is clean.
4. Check for ProGuard impacts (Moshi adapters, Retrofit, OkHttp have reflection concerns).
5. Verify the app functions correctly (OG fetch, Gemini summary, Room operations).

### User data sent to unintended network endpoint
NexRe's privacy contract: only the URL being saved goes to the network (OG fetch), and link content goes to Gemini only if the user opted in with their own API key.
- Audit any new network call: what data is sent? Is it user-initiated? Is it HTTPS?
- Remove any analytics, tracking, or telemetry code immediately.

### HTTP instead of HTTPS for Gemini calls
- Retrofit base URL: `https://generativelanguage.googleapis.com` — must remain HTTPS.
- OkHttp client: do not add `hostnameVerifier { _, _ -> true }` or disable certificate validation.

### PII in logcat
- Search for `Log.d`, `Log.e`, `Log.w`, `Log.i` calls that include `link.summary`, `link.personalNote`, `link.description`, or the API key.
- Remove or replace with a non-sensitive placeholder.

## Steps

1. Identify root cause.
2. Apply the minimal fix — don't refactor surrounding code.
3. Verify the fix closes the issue.
4. Run `bash gates/scripts/verify-kotlin.sh`.
5. Check `core/definition-of-done.md` — security section.

## Done

All boxes in `core/definition-of-done.md` are checked, especially the Security and Privacy sections.
