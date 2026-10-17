# SEC/IAPD Wayback availability V6.1 execution hardening

## Purpose

V6.1 is an execution-only safety amendment for the already frozen V6 release.
It does not change the V6 candidate population, input hashes, cooldown,
availability semantics, or result verifier.

For real V6 execution, the authoritative module is now:

```powershell
.venv\Scripts\python.exe -m scripts.retry_sec_edgar_iapd_wayback_availability_v6_1 --release configs/sec_edgar_iapd_wayback_availability_retry_release_v6.json
```

The older `scripts.retry_sec_edgar_iapd_wayback_availability_v6` module remains
frozen for provenance, but is superseded for execution. The frozen V6 config
and `scripts.verify_sec_edgar_iapd_wayback_availability_result_v6` remain in
force.

## Fail-closed execution protocol

1. Revalidate every V6 basis/input hash, the V5 independent-QA status, all 115
   ordered identities, the eight-row unresolved-only population, and the
   authorization/safety flags.
2. Read `created_at` from the actual hash-pinned V5 parent report. Require the
   release's `prior_attempt_created_at` to name that same instant and require
   `not_before` to equal that instant plus 86,400 seconds.
3. Refuse execution before `not_before`.
4. Refuse execution if either the final V6 output or its `.partial` journal
   already exists. A partial is evidence of a prior start and is never resumed
   automatically.
5. Atomically create and flush an exclusive `.partial` reservation before the
   first network request.
6. Retry only the eight unresolved V5 rows, once each, through the pinned HTTPS
   archive availability endpoint and exact host allowlist. Preserve all 107
   resolved V5 result objects without modification.
7. After every attempted candidate, atomically replace and flush the partial
   journal. It records completed attempts, pending IDs, request count, and the
   explicit `resume_allowed: false` guard.
8. Stop immediately after HTTP 429. Do not contact later candidates.
9. Only after normal completion, atomically replace the partial journal with
   the final V6 report.

## Scope and gates

- Minimum delay remains 60 seconds.
- Maximum logical attempts remain one per unresolved candidate.
- Candidate live domains are never accessed.
- No archived page is downloaded and no artifact is captured.
- Availability is never treated as a content label.
- Capture planning remains closed unless the independent V6 result verifier
  confirms that all 115 rows are resolved.
- Labeling, model training, validation, and test remain closed.

## Offline verification

The mocked V6.1 tests cover:

- pre-gate refusal without creating a reservation;
- simulated failure after the first request with a durable, non-resumable
  partial checkpoint;
- final/partial no-overwrite refusal before networking;
- immediate HTTP 429 stop;
- successful completion with byte-equivalent preservation of resolved V5
  rows and atomic finalization.

These tests perform no network operations and do not execute the real V6
release.
