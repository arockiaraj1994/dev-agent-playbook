---
title: Release — NexRe
description: Playbook for bumping the version, building a release bundle, and installing via ADB.
triggers: [release, publish, bump version, adb install, install apk, release bundle, play store, version code, version name]
see_also: [gates:README]
---

# Skill: Release — NexRe

## Scripts

All scripts live in `dev-agent-playbook/nexre/gates/scripts/` and are run from any location.
They default to `NEXRE_ROOT=/home/arockiaraj/Documents/Projects/NexRe`.

---

## 1. Bump version

```bash
bash gates/scripts/bump-version.sh patch          # 1.0.2 → 1.0.3, versionCode +1
bash gates/scripts/bump-version.sh minor          # 1.0.2 → 1.1.0, versionCode +1
bash gates/scripts/bump-version.sh major          # 1.0.2 → 2.0.0, versionCode +1
bash gates/scripts/bump-version.sh set 1.2.0 10  # explicit values
```

Edits `versionCode` and `versionName` in `app/build.gradle.kts` in-place.

---

## 2. Build release bundle (Play Store)

```bash
bash gates/scripts/build-release-bundle.sh
```

Runs `./gradlew bundleRelease`. Output: `app/build/outputs/bundle/release/app-release.aab`.

Requires `app/keystore.properties` for a signed bundle.

---

## 3. Install APK via ADB

```bash
bash gates/scripts/adb-install.sh           # debug APK (default)
bash gates/scripts/adb-install.sh release   # release APK
```

Builds the variant and runs `adb install -r` on the connected device/emulator.

---

## Typical release flow

```bash
# 1. bump version
bash gates/scripts/bump-version.sh patch

# 2. commit the version change
git -C "$NEXRE_ROOT" add app/build.gradle.kts
git -C "$NEXRE_ROOT" commit -m "chore: bump version to $(grep versionName $NEXRE_ROOT/app/build.gradle.kts | grep -oP '\"\\K[^\"]+') (versionCode $(grep versionCode $NEXRE_ROOT/app/build.gradle.kts | grep -oP '\d+'))"

# 3. build and verify
bash gates/scripts/verify-kotlin.sh

# 4. build release bundle for Play Store
bash gates/scripts/build-release-bundle.sh

# 5. (optional) install on device for smoke test
bash gates/scripts/adb-install.sh release
```
