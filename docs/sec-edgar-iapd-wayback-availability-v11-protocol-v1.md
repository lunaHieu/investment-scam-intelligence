# SEC/IAPD Wayback Availability V11 Protocol V1

Date: 2026-10-23  
Status: offline tooling frozen; concrete execution release intentionally absent

## Step name and meaning

This is plan step A2. It prepares a new availability executor, release
verifier, result verifier, and exact-two-row protocol for the two unresolved
external-holdout records left by V10. It does not reuse the V10 executor and
does not authorize a network request.

The exact ordered population is:

1. `TTCV1_EDGAR_AVAIL_HOLDOUT_011` — `murphyllc.com`;
2. `TTCV1_EDGAR_AVAIL_HOLDOUT_018` — `wealthmanage.net`.

V10 queried the first row and received HTTP 429. It stopped before querying
the second row. Both remain unresolved; neither is interpreted as unavailable,
available, legitimate, confirmed, or training eligible.

## New V11 safeguards

- descriptive User-Agent with tool version, `gpt-5`, and public project URL;
- at least 60 seconds before every archive request;
- one logical attempt per authorized row;
- immediate stop on HTTP 429;
- preservation of `Retry-After`, `Date`, `Server`, `Content-Type`, and
  `X-Archive-Wayback-Runtime-Error`;
- partial journal reserved before network and checkpointed after every row;
- no automatic resume and no overwrite;
- exact preservation of all 113 resolved V10 rows;
- no candidate live-domain access and no archived-page download.

## Why no concrete release is frozen yet

The alternate-snapshot CDX A1 release is scheduled to make a later archive
metadata request. That real request, if executed, becomes the newest cooldown
anchor. Freezing V11 now against the older request would create a stale or
misleading `not_before`.

Therefore the protocol requires a future concrete V11 release to be created
only after the latest actual archive request is known. The release must bind
the exact report path, SHA-256, and `created_at`, and its `not_before` must be at
least 24 hours later. The release verifier rejects a shorter or stale binding.

## Downstream meaning

A resolved V11 availability row remains supplemental metadata. It cannot
mutate the completed 58-row capture plan or frozen 56-row review population.
Any newly available snapshot requires a separate supplemental capture plan,
release, byte/hash QA, extraction, grouping, review, reconciliation, and owner
acceptance. This protocol creates no label and opens no model gate.
