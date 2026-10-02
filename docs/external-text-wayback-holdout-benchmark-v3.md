# External text Wayback holdout benchmark V3

## Outcome

V3 freezes a completely new, balanced English external holdout with 30 records: 15 `CONFIRMED` and 15 `LEGITIMATE`. Every materialized record uses the same capture stratum (`WAYBACK_ARCHIVED_HOMEPAGE_HTML`) and has high-confidence agreement between an AI primary review and an independent blinded AI second review.

The benchmark is not training data. Model scoring remains blocked until owner acceptance is recorded after this freeze.

## Acquisition and review funnel

| Stage | Result |
|---|---:|
| New hosts queued | 200 (100 per reference branch) |
| Prior-queue and opened-V2 host overlap | 0 |
| Archive-available hosts | 130 |
| Balanced capture plan | 74 (37 per branch) |
| Captured | 70 |
| Hash-verified readable captures | 69 |
| Deterministic balanced usable view | 64 (32 per branch) |
| Reviewable after offline screening | 47 |
| Primary AI review | 17 `CONFIRMED`, 30 `LEGITIMATE` |
| English high-confidence candidates sent to blind review | 32 (16 per class) |
| High-confidence agreements | 30 (15 per class) |
| Frozen English benchmark | 30 (15 per class) |

## Review decisions

Automatic language detection was routing help only. Manual review corrected `diaphanum.com` from the automatic non-English bucket to English because the substantive captured service description is English. `fortevalbit.it` is the one non-English capture and remains a reserve because no balanced non-English cohort meets the six-per-class protocol minimum.

The second reviewer received only opaque blind IDs, archived visible text, and the relevant official reference. It did not receive the private mapping, first review, candidate provenance branch, model outputs, or earlier conversation.

Two same-decision cases were excluded because the second reviewer assigned `MEDIUM`, not `HIGH`, confidence:

- `MATCHWB3_CONF_025`: alternate company language, a different-domain support email, and an unverified regulation claim reduced confidence.
- `MATCHWB3_LEGIT_047`: an unrelated template contact block contaminated an otherwise aligned registered-adviser capture.

No decision was upgraded to meet the target size. The frozen benchmark is the natural high-confidence intersection.

## Leakage and use contract

Only `records[].artifact.visible_text` may later be supplied to a model. Regulator warnings, registration records, reviewer rationales, labels, mappings, and provenance are evaluation metadata and must never enter model input.

The benchmark is external evaluation data only:

- training: blocked;
- tuning or threshold selection: blocked;
- deployment decisions: blocked;
- model scoring: blocked until owner acceptance is recorded;
- independent human review: not claimed.

## Verification

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\verify_external_text_wayback_holdout_benchmark_v3.py --registry registry\pilots\external_text_wayback_holdout_benchmark_v3.json
```

The verifier checks every registry hash, the 47 primary packet raw-capture hashes, text hashes, review agreement, class balance, the English minimum, and the closed scoring/training gates.
