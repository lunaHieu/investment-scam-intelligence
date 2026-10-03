# Target Text Corpus V1 candidate enumeration V1

Status: **40-row balanced provenance queue frozen; independent QA passed; capture and labels remain blocked**.

## Purpose

This milestone converts four separately normalized official-reference pools into a small, auditable schema-review queue. It is not a labeled dataset and it is not used for model training. The queue exists so that later Wayback capture and human adjudication can be performed against a fixed candidate population without quietly changing the sample after seeing its content.

## Authorized reference acquisition

The acquisition phase fetched only official CFTC and SEC reference artifacts. It made 17 CFTC requests (two RED List pages and fifteen detail pages) and 22 SEC requests (two transfers of the company-ticker reference plus twenty submissions files). It made zero requests to any candidate domain. The private SEC identity file remains outside the repository; its path, content, email address, and hash are intentionally absent from the public registry.

The reference evidence was normalized into four disjoint channel pools:

- IOSCO/regulator warnings for `CONFIRMED_REGULATOR_LINKED_WEBSITE`;
- CFTC RED List entries for `CONFIRMED_CFTC_RED_LINKED_WAYBACK_WEBSITE`;
- SEC IAPD registration references for `LEGITIMATE_REGISTER_LINKED_WEBSITE`; and
- SEC EDGAR submissions cross-walked to IAPD entities for `LEGITIMATE_SEC_EDGAR_LINKED_WAYBACK_WEBSITE`.

The CFTC hosts were reserved out of the regulator-warning pool, and the EDGAR-selected entities were reserved out of the IAPD pool. This makes channel membership disjoint before enumeration instead of resolving collisions after selection.

## Enumeration result

The frozen deterministic selector emitted exactly 40 candidates: ten from each channel. It refused quota reallocation and excluded previously opened hosts, within-channel duplicate hosts, cross-channel duplicate hosts, and cross-stratum entity collisions. The eligible pools at selection time were 12,055 regulator rows, 12 CFTC hosts, 3,647 IAPD rows, and 20 EDGAR rows.

Every candidate remains:

- `ground_truth_status: UNCERTAIN`;
- `review_state: UNREVIEWED`;
- `training_eligible: NO`;
- `label_created: false`; and
- uncaptured, with no live-domain access.

Source channel is provenance, not a binary label. A regulator-linked candidate is not automatically `CONFIRMED`, and a register-linked candidate is not automatically `LEGITIMATE`.

## Independent QA

The independent verifier reloaded the frozen queue and source pools, validated the candidate schema, checked unique IDs and hosts, confirmed zero overlap with the opened-host exclusion index, reproduced the deterministic selection, and verified every referenced source artifact hash. All checks passed.

The production queue SHA-256 is `32f19c38a0d77aa5707b1ff7f0adbfa44409426632ce9af51e70286c2c076a67`.

## Current gate

This registry closes only the enumeration milestone. Candidate capture, manual binary adjudication, training eligibility, validation/test access, and model operations remain blocked. The next separately versioned step is a Wayback-only availability/capture plan that preserves this queue and does not access live candidate domains.
