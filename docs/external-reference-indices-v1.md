# External reference indices V1

## Purpose

This stage turns the pinned IOSCO I-SCAN CSV and SEC/IAPD firm XML into small,
deterministic lookup indices for later evidence review. It does not create model
labels, train a model, open listed domains, or resolve an entity automatically.

## Meaning of each source

- An IOSCO match means that a regulator warning record may be relevant. It is not
  a criminal conviction or a complete scam label. No match does not prove safety.
- An SEC/IAPD match means that a registered or exempt-reporting firm with similar
  identifying information exists. It is not a content-safety label and does not
  prove that the operator of a matching-looking website is that firm.

## Retained fields

The indices retain the pinned source/version/hash, public source record ID,
normalized entity-name keys, canonical hostnames, limited registration or warning
metadata, evidence dates, and the official IOSCO notice URL. IOSCO narratives and
SEC postal addresses, telephone numbers, and fax numbers are excluded.

Name normalization uses Unicode NFKC, case folding, punctuation-to-space, and
whitespace collapse. Values containing the Unicode replacement character are not
used as name keys. Host normalization is offline and does not claim registrable
domain boundaries; it lowercases/IDNA-encodes the parsed hostname and removes only
an initial `www.`.

## Required use policy

Any later match is a review candidate, not a conclusion. Human review must compare
the name, hostname, regulator reference, dates, source context, and impersonation
risk. Exact or normalized matches must never be copied directly into training as
`scam` or `legitimate` labels.

## Rebuild command

Run `scripts/build_external_reference_indices.py` with explicit IOSCO output, SEC
output, and report paths. The script verifies both raw SHA-256 hashes first and
refuses to overwrite existing frozen artifacts.

## Frozen artifacts (2026-09-23)

- IOSCO warning-reference index: 47,001 records; 43,433 have a usable
  entity-name key and 19,192 have an observed hostname. SHA-256:
  `578b2681f8d638d7b1a4d19882fc40b26965e397cef24f5a452f76cac229a5e2`.
- SEC/IAPD registration-reference index: 23,927 records; all have a usable
  entity-name key and 21,071 have an observed hostname. SHA-256:
  `7004453a5e5e71747f4f8b2f65cb79ed9359c482fd7f3f2abedfa75540890807`.
- Shared build report SHA-256:
  `034c180763da4c83e73757a98991eb591832cd1f17ab864680cb6cc690d9b3b8`.

Missing hostname coverage is preserved as missingness; it is not filled by web
search. Duplicate normalized names or hosts remain separate source records and
must not be collapsed without manual evidence review.
