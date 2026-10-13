# SEC EDGAR submissions bulk V1 retry release V2

## Step name

Diagnose the failed-closed acquisition and issue one controlled retry.

## Meaning

The first request was consumed but created no raw artifact or manifest because the archive contained a non-JSON-suffixed member. The safety-relevant ZIP checks worked: the partial file was deleted and nothing downstream was opened.

The corrected tooling still rejects unsafe paths, duplicates, encryption, empty/no-JSON archives, and CRC failures. It now records aggregate extension counts and keeps non-JSON members inert inside the immutable ZIP. Later extraction must explicitly select JSON members only. This retry is separately hash-bound and is consumed by its single network request, regardless of outcome.
