---
title: Gates — Apache Camel
description: Executable verification scripts that close out a task.
tags: [gates, ci, definition-of-done]
---

# Gates — Apache Camel

A "gate" is a script you run before claiming a task complete. It enforces
the mechanical checks in `core/definition-of-done.md`. The MCP server does
not execute these scripts; CI and developers do.

## verify-java.sh

Compiles, runs tests, format-checks, static-analyses, and dependency-scans
the project. Exits non-zero on any failure.

```
bash gates/scripts/verify-java.sh
```

What it runs (in order):

1. `mvn -q -DskipTests verify` — compile + package.
2. `mvn -q spotless:check` — format (skipped if Spotless isn't configured).
3. `mvn -q spotbugs:check` — static analysis (skipped if SpotBugs isn't configured).
4. `mvn -q test` — unit and integration tests.
5. `mvn -q dependency-check:check` — CVE scan (skipped if not configured).

Each step that isn't configured for the project is skipped with a notice;
the script does NOT silently pass over a configured step that fails.

## Adding a new gate

Drop a new `verify-<name>.sh` under `gates/scripts/`, mark it executable
(`chmod +x`), and document it here. The validator will fail if the script
is not executable.
