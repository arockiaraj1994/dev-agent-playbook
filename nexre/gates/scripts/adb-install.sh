#!/usr/bin/env bash
set -euo pipefail

# Install debug or release APK on connected device/emulator via ADB.
# Usage:
#   bash gates/scripts/adb-install.sh          # installs debug APK
#   bash gates/scripts/adb-install.sh release  # installs release APK
#   NEXRE_ROOT=/path/to/NexRe bash gates/scripts/adb-install.sh

NEXRE_ROOT="${NEXRE_ROOT:-/home/arockiaraj/Documents/Projects/NexRe}"
VARIANT="${1:-debug}"

if [ ! -f "$NEXRE_ROOT/gradlew" ]; then
    echo "ERROR: NexRe project not found at $NEXRE_ROOT"
    echo "Set NEXRE_ROOT env var to the correct path."
    exit 1
fi

if ! command -v adb &>/dev/null; then
    echo "ERROR: adb not found in PATH. Install Android SDK platform-tools."
    exit 1
fi

DEVICE_COUNT=$(adb devices | tail -n +2 | grep -c "device$" || true)
if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo "ERROR: No ADB devices/emulators connected. Run 'adb devices' to check."
    exit 1
fi

cd "$NEXRE_ROOT"

if [ "$VARIANT" = "release" ]; then
    APK_PATH="app/build/outputs/apk/release/app-release.apk"
    echo "=== Building release APK ==="
    ./gradlew assembleRelease
else
    APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
    echo "=== Building debug APK ==="
    ./gradlew assembleDebug
fi

if [ ! -f "$APK_PATH" ]; then
    echo "ERROR: APK not found at $APK_PATH after build."
    exit 1
fi

echo "=== Installing $APK_PATH ==="
adb install -r "$APK_PATH"

echo ""
echo "OK — NexRe ($VARIANT) installed on device"
