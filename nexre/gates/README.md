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

---

## adb-install.sh

```bash
bash gates/scripts/adb-install.sh           # debug (default)
bash gates/scripts/adb-install.sh release   # release
```

Builds the selected variant and installs it on the connected device/emulator via `adb install -r`.

### Requirements

- `adb` must be in `PATH` (Android SDK platform-tools).
- At least one device/emulator must be connected (`adb devices`).
- Release variant requires `app/keystore.properties`.

---

## build-release-bundle.sh

```bash
bash gates/scripts/build-release-bundle.sh
```

Runs `./gradlew bundleRelease` and prints the output AAB path with current version info.

### Output

`app/build/outputs/bundle/release/app-release.aab` — upload this to Play Store.

---

## bump-version.sh

```bash
bash gates/scripts/bump-version.sh patch          # 1.0.2 → 1.0.3, versionCode +1
bash gates/scripts/bump-version.sh minor          # 1.0.2 → 1.1.0, versionCode +1
bash gates/scripts/bump-version.sh major          # 1.0.2 → 2.0.0, versionCode +1
bash gates/scripts/bump-version.sh set 1.2.0 10  # explicit versionName and versionCode
```

Updates `versionCode` and `versionName` in `app/build.gradle.kts` in-place.

### Typical release flow

```bash
bash gates/scripts/bump-version.sh patch
bash gates/scripts/build-release-bundle.sh
# upload AAB to Play Store
```
