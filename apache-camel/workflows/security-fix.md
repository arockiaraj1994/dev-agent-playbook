---
title: Workflow — Security fix
description: Patching a CVE, removing a leaked secret, or tightening transport security.
triggers: [security fix, cve, vulnerability, leaked secret, credential leak, tls, ssl, dependency upgrade]
gates: [verify-java]
see_also: [pattern:error-handling, language:java/standards, language:java/anti-patterns]
---

# Workflow — Security fix

Use this when the trigger is a security advisory, scanner finding, or
discovered secret. Speed matters but correctness matters more — security
fixes are the fastest path to incident.

## Steps

1. **Categorise.** Is this (a) a vulnerable dependency, (b) a leaked secret in code/history, (c) an insecure transport (`http://`, disabled TLS verification), or (d) an authorization gap? Each branch has different urgency.
2. **Contain first if needed.** For an active leak, **rotate the credential before the code change.** A code fix that leaves the leaked value valid is theatre.
3. **Fix the underlying issue.**
   - **Vulnerable dependency:** bump the Maven coordinate; verify the fix version actually addresses the CVE (check the advisory).
   - **Leaked secret:** remove from code AND from git history if reachable. Re-issue via env var / Kubernetes Secret. Audit logs for unauthorized use.
   - **Insecure transport:** switch to `https://`, re-enable certificate verification, pin TLS minimum version where supported.
   - **Authorization gap:** add the missing check at the route boundary, not deep inside a processor.
4. **Regression test.** A test that proves the vulnerable behavior is gone (e.g. unit test asserting cert verification is on).
5. **Scan again.** `mvn -q dependency-check:check` or the project-configured scanner — the finding should be gone.
6. **Run the gate.** `bash gates/scripts/verify-java.sh`.
7. **Notify.** Security fixes ship fast; loop in the owning team and update the advisory tracker.

## MUST NOT

- Skip rotation when secrets leaked. Code change without rotation = still compromised.
- Pin a CVE to "ignored" in the scanner without a written justification.
- Disable TLS verification "temporarily." Temporary becomes permanent.
