#!/usr/bin/env bash
set -euo pipefail

# Bump versionCode and/or versionName in app/build.gradle.kts.
# Usage:
#   bash gates/scripts/bump-version.sh patch          # 1.0.2 → 1.0.3, versionCode +1
#   bash gates/scripts/bump-version.sh minor          # 1.0.2 → 1.1.0, versionCode +1
#   bash gates/scripts/bump-version.sh major          # 1.0.2 → 2.0.0, versionCode +1
#   bash gates/scripts/bump-version.sh set 1.2.0 10  # explicit versionName + versionCode
#
# NEXRE_ROOT=/path/to/NexRe bash gates/scripts/bump-version.sh patch

NEXRE_ROOT="${NEXRE_ROOT:-/home/arockiaraj/Documents/Projects/NexRe}"
GRADLE="$NEXRE_ROOT/app/build.gradle.kts"

if [ ! -f "$GRADLE" ]; then
    echo "ERROR: build.gradle.kts not found at $GRADLE"
    echo "Set NEXRE_ROOT env var to the correct path."
    exit 1
fi

BUMP="${1:-patch}"

CURRENT_CODE=$(grep 'versionCode' "$GRADLE" | grep -oP '\d+')
CURRENT_NAME=$(grep 'versionName' "$GRADLE" | grep -oP '"\K[^"]+')

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_NAME"

case "$BUMP" in
  set)
    NEW_NAME="${2:?Usage: bump-version.sh set <versionName> <versionCode>}"
    NEW_CODE="${3:?Usage: bump-version.sh set <versionName> <versionCode>}"
    ;;
  major)
    NEW_NAME="$((MAJOR + 1)).0.0"
    NEW_CODE="$((CURRENT_CODE + 1))"
    ;;
  minor)
    NEW_NAME="${MAJOR}.$((MINOR + 1)).0"
    NEW_CODE="$((CURRENT_CODE + 1))"
    ;;
  patch)
    NEW_NAME="${MAJOR}.${MINOR}.$((PATCH + 1))"
    NEW_CODE="$((CURRENT_CODE + 1))"
    ;;
  *)
    echo "ERROR: Unknown bump type '$BUMP'. Use: patch | minor | major | set <name> <code>"
    exit 1
    ;;
esac

echo "  versionCode : $CURRENT_CODE → $NEW_CODE"
echo "  versionName : $CURRENT_NAME → $NEW_NAME"

sed -i "s/versionCode = $CURRENT_CODE/versionCode = $NEW_CODE/" "$GRADLE"
sed -i "s/versionName = \"$CURRENT_NAME\"/versionName = \"$NEW_NAME\"/" "$GRADLE"

echo ""
echo "OK — $GRADLE updated"
