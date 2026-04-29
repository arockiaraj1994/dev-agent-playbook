#!/usr/bin/env bash
# verify-java.sh — definition-of-done gate for Apache Camel projects.
#
# Runs compile, format, static analysis, tests, and a dependency scan.
# Skips steps the project hasn't configured; never silently passes a
# configured-but-failing step.

set -euo pipefail

if ! command -v mvn >/dev/null 2>&1; then
  echo "verify-java: mvn not on PATH — install Maven before running this gate." >&2
  exit 2
fi

run_if_configured() {
  local label="$1"
  local probe="$2"
  shift 2
  if mvn -q help:describe -Dplugin="${probe}" >/dev/null 2>&1; then
    echo "==> ${label}"
    "$@"
  else
    echo "-- ${label}: skipped (plugin '${probe}' not configured)"
  fi
}

echo "==> compile + package (skip tests)"
mvn -q -DskipTests verify

run_if_configured "spotless:check" "com.diffplug.spotless:spotless-maven-plugin" \
  mvn -q spotless:check

run_if_configured "spotbugs:check" "com.github.spotbugs:spotbugs-maven-plugin" \
  mvn -q spotbugs:check

echo "==> tests"
mvn -q test

run_if_configured "dependency-check:check" "org.owasp:dependency-check-maven" \
  mvn -q dependency-check:check

echo "OK"
