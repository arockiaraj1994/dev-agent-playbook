#!/usr/bin/env bash
set -euo pipefail

# Build a signed release AAB (Android App Bundle) for Play Store upload.
# Usage:
#   bash gates/scripts/build-release-bundle.sh
#   NEXRE_ROOT=/path/to/NexRe bash gates/scripts/build-release-bundle.sh
#
# Requires app/keystore.properties to be present with signing config.

NEXRE_ROOT="${NEXRE_ROOT:-/home/arockiaraj/Documents/Projects/NexRe}"

if [ ! -f "$NEXRE_ROOT/gradlew" ]; then
    echo "ERROR: NexRe project not found at $NEXRE_ROOT"
    echo "Set NEXRE_ROOT env var to the correct path."
    exit 1
fi

if [ ! -f "$NEXRE_ROOT/app/keystore.properties" ]; then
    echo "WARN: app/keystore.properties not found — bundle will be unsigned."
    echo "      Add signing config before uploading to Play Store."
fi

cd "$NEXRE_ROOT"

VERSION_CODE=$(grep 'versionCode' app/build.gradle.kts | grep -oP '\d+')
VERSION_NAME=$(grep 'versionName' app/build.gradle.kts | grep -oP '"\K[^"]+')

echo "=== Building release bundle (versionCode=$VERSION_CODE, versionName=$VERSION_NAME) ==="
./gradlew bundleRelease

AAB_PATH="app/build/outputs/bundle/release/app-release.aab"

if [ ! -f "$AAB_PATH" ]; then
    echo "ERROR: AAB not found at $AAB_PATH after build."
    exit 1
fi

echo ""
echo "OK — Release bundle: $AAB_PATH"
echo "     versionCode : $VERSION_CODE"
echo "     versionName : $VERSION_NAME"
