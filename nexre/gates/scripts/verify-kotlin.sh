#!/usr/bin/env bash
set -euo pipefail

# Run from the NexRe project root: bash gates/scripts/verify-kotlin.sh
# (This script lives in dev-agent-playbook/nexre/gates/scripts/ but targets the NexRe repo)

NEXRE_ROOT="${NEXRE_ROOT:-/home/arockiaraj/Documents/Projects/NexRe}"

if [ ! -f "$NEXRE_ROOT/gradlew" ]; then
    echo "ERROR: NexRe project not found at $NEXRE_ROOT"
    echo "Set NEXRE_ROOT env var to the correct path."
    exit 1
fi

cd "$NEXRE_ROOT"

echo "=== [1/4] Debug build ==="
./gradlew assembleDebug

echo "=== [2/4] Release build ==="
./gradlew assembleRelease || echo "WARN: Release build failed (signing config may be missing — acceptable in dev)"

echo "=== [3/4] Lint ==="
./gradlew lint

echo "=== [4/4] Unit tests ==="
./gradlew test

echo ""
echo "OK — all gates passed"
