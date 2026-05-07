---
title: Gates — NexRe
description: Executable verification scripts for NexRe builds.
---

# Gates — NexRe

## verify-kotlin.sh

```bash
bash gates/scripts/verify-kotlin.sh
```

Run this from the **NexRe project root** (`/home/arockiaraj/Documents/Projects/NexRe`).

### What it runs

| Step | Command | Passes when |
|------|---------|-------------|
| Debug build | `./gradlew assembleDebug` | Zero compilation errors |
| Release build | `./gradlew assembleRelease` | R8/minification clean, signing present or skipped |
| Lint | `./gradlew lint` | Zero new errors |
| Unit tests | `./gradlew test` | All tests pass (no failures or errors) |

### When to run

- Before claiming any task complete.
- After adding a new dependency.
- After any Room schema change (also manually test migration on a device).
- After editing ProGuard rules.

### Notes

- The release build requires `app/keystore.properties` with signing config. If it's absent, the release build uses no signing — this is expected in a dev environment without the keystore.
- Lint may report existing warnings in unchanged code — only new warnings introduced by your change count as a gate failure.
