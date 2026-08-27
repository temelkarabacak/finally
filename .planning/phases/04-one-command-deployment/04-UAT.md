---
status: complete
phase: 04-one-command-deployment
source: [04-VERIFICATION.md]
started: 2026-08-27T00:00:00Z
updated: 2026-08-27T09:20:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Browser-tab wall-clock shutdown confirmation
expected: With `finally-app` running and a real browser tab open on `http://localhost:8000` (genuine `EventSource`, not curl), run `docker stop --timeout 15 finally-app` and time it. Returns within roughly 10-15 seconds, no manual force-kill needed. This is 04-01-PLAN.md's own Task 2 human-check — a curl-based SSE reader (live-measured at 11-13s across three runs) approximates but does not fully reproduce a browser EventSource connection's SIGTERM behavior.
result: pass

### 2. Real-Windows PowerShell lifecycle run
expected: On a real Windows machine with Docker Desktop, run `.\scripts\start_windows.ps1` twice, browse to the app, then `.\scripts\stop_windows.ps1` twice, then `.\scripts\start_windows.ps1` again to confirm the portfolio survived. Both start runs exit 0 (idempotent, one container); both stop runs exit 0 (idempotent); portfolio data survives the cycle. This is 04-02-PLAN.md's own Task 2 human-check — no Windows host or pwsh was available in the executor's or verifier's environment.
result: pass

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None — both items are pre-declared human-checks from the plans themselves, not gaps discovered during verification. All 20 automated must-have truths passed live re-verification (see 04-VERIFICATION.md).
