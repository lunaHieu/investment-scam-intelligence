# SEC/IAPD V9 Rate-Limit Incident Analysis V1

Date: 2026-10-21
Scope: offline analysis of immutable availability reports V1–V9

## Conclusion

The confirmed failure is an HTTP 429 returned by the Wayback availability
endpoint on the first V9 request. The stored evidence does not identify the
controlling quota, so shared-IP quota, endpoint-wide load control and a broader
historical request quota remain hypotheses rather than proven root causes.

The repeated 24-hour cooldown has not been an effective predictor of success.
V6, V7, V8 and V9 each ran more than 24 hours after the preceding material run
and still ended in HTTP 429. V5, by contrast, completed 23 requests without a
429 after approximately 31.5 hours. The available evidence therefore supports
intermittent or externally shared throttling, but not a precise duration-based
quota model.

## Evidence timeline

| Report | Created at (+07:00) | Requests in run | Result |
|---|---:|---:|---|
| V1 | 2026-10-13 23:16:56 | 51 | five timeouts, then HTTP 429 |
| V2 | 2026-10-13 23:20:18 | 2 | DNS failure, then HTTP 429 |
| V3 | 2026-10-15 00:48:55 | 70 | no 429; timeout/DNS failures preserved |
| V4 | 2026-10-16 01:19:27 | 10 | connection failure, then HTTP 429 |
| V5 | 2026-10-17 08:47:59 | 23 | no 429; eight connection/DNS failures |
| V6 | 2026-10-18 09:45:26 | 1 | HTTP 429 on first request |
| V7 | 2026-10-19 14:06:35 | 7 | six rows resolved, then HTTP 429 |
| V8 | 2026-10-20 14:19:54 | 2 | DNS failure, then HTTP 429 |
| V9 | 2026-10-21 18:18:58 | 1 | HTTP 429 on first request |

V9 preserved 113 resolved rows unchanged: 58 available and 55 unavailable.
Only `TTCV1_EDGAR_AVAIL_HOLDOUT_011` and
`TTCV1_EDGAR_AVAIL_HOLDOUT_018` remain quarantined. The second V9 row was not
requested because the executor correctly stopped after the first 429.

## Observability gap

The V9 executor recorded the status and error text, but discarded response
headers. Consequently the report cannot show whether Wayback supplied
`Retry-After`, which server handled the response, or an archive-specific error
header. No extra network probe is justified merely to recover missing
diagnostics. Future network executors should preserve a small allowlisted set
of non-sensitive response headers when an HTTP error occurs.

## Impact boundary

- No prior availability result, identity, cohort or hash changed.
- No live candidate domain was contacted.
- No raw archive capture was attempted during V9.
- The two unresolved availability rows remain unlabeled and quarantined.
- The separately verified 58-row V5 capture population is unchanged and does
  not contain either unresolved row.
- Validation, test, training and scoring remain closed.

The incident therefore affects the two-row availability retry and confidence
about Wayback service health. It does not invalidate the 58 frozen available
snapshots.

## Recovery decision

V10 remains binding for the two unresolved rows and must not run before its
frozen time. It is no longer treated as a prerequisite for the independent
58-row V5 capture. Capture may proceed in a separate process under the original
V5 not-before, archive-only allowlist, 30-second minimum pacing, one attempt per
snapshot, immediate stop on 429, no overwrite and independent byte/hash QA.

Before capture, use a versioned crash-safe executor that reserves a journal
before network access and checkpoints after every row. This closes a discovered
implementation gap in the original executor, which wrote raw files throughout
the run but wrote its report only at the end. The new executor must also retain
allowlisted HTTP diagnostic headers on failure. A partial journal is never
automatically resumed.

