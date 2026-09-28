# External Source Acquisition Log — 2026-09-23

This log records the public-source acquisition performed after the external text intake gate was frozen. It does not promote any record to Gold, does not open the internal test set, and does not authorize model scoring.

## Acquired and verified

### IOSCO I-SCAN

- Canonical source: <https://www.iosco.org/i-scan/>
- Acquisition method: the portal's visible **Export to CSV** control.
- Raw path: `D:/nckh 2026-2027/ISI_Data/raw/iosco_i_scan/I-SCAN Export.csv`
- File size: 16,857,039 bytes.
- SHA-256: `2d592f2e8b4fda6d6d9ba102571561a7e3bb00150e9eb24849c919b28c0458ab`.
- Structural check: 47,001 parsed records and 27 columns; latest `validation_date` observed in the export is 2026-09-21.
- Interpretation guardrail: I-SCAN is an incomplete registry of member alerts. A record is warning evidence, not a conviction; no match is not a legitimacy signal.

### SEC Investment Adviser Public Disclosure

- Canonical source: <https://adviserinfo.sec.gov/compilation>
- Source release: `IA_FIRM_SEC_Feed_09_22_2026` (report as of 2026-09-22).
- Raw path: `D:/nckh 2026-2027/ISI_Data/raw/sec_iapd/IA_FIRM_SEC_Feed_09_22_2026.xml.gz`
- File size: 7,301,031 compressed bytes and 82,577,437 decompressed bytes.
- SHA-256: `262b2151a6d6289119a104fd03ea6fbc9d44c38c7f4c52584865244777f65366`.
- Structural check: gzip stream completed, XML root is `IAPDFirmSECReport`, and 23,927 `Firm` elements were parsed.
- Interpretation guardrail: registration is an entity-reference signal, not proof that a message, website, representative, or investment offer is legitimate. Impersonation remains possible.

## Verified but not yet persisted

### DFPI Crypto Scam Tracker

- Canonical source: <https://dfpi.ca.gov/consumers/crypto/crypto-scam-tracker/>
- Visible portal state on 2026-09-23: 604 entries; page states it was updated 2026-09-11.
- Browser review covered all seven pages at 100 rows per page (100 + 100 + 100 + 100 + 100 + 100 + 4).
- Direct HTTP acquisition remains blocked by Cloudflare. The controlled browser allowed viewing the public table but blocked creation of a local export artifact from rendered data.
- No bypass was attempted. The raw directory remains empty and no DFPI manifest has been created.
- Interpretation guardrail: DFPI says the tracker is based on consumer complaints and that reported losses have not been verified. Records require corroboration before a confirmed label.

## Next gate

### Read-only profile artifact

- Path: `D:/nckh 2026-2027/ISI_Data/derived/external_reference_profiles_v1/source_profile_v1.json`
- File size: 14,802 bytes.
- SHA-256: `d01fd4c359fd44a77043bbe15c843f8c2d6d77ba8652e8a70d5c53186ab86f75`.
- Safety result: zero network operations during profiling, raw files unchanged, zero labels created, zero model-scoring operations, and training remains blocked.
- IOSCO quality finding: no duplicate non-empty IDs; four Unicode replacement characters are present across two raw rows, confined to `commercial_name`. Preserve the raw bytes and handle this only in a future derived normalization layer.
- SEC quality finding: no duplicate non-empty CRD numbers; all 23,927 firms contain CRD, SEC number, business name, and legal name; 21,072 firms contain at least one web address.

1. Treat IOSCO and SEC files as immutable raw sources and verify them with `scripts/verify_raw_data.py`.
2. Build read-only source profiles before any normalization.
3. Keep IOSCO records in the warning/evidence branch and SEC records in the legitimate-reference branch.
4. Do not use either source as direct binary training labels.
5. Acquire DFPI later through a first-party downloadable export or a user-saved browser artifact; do not bypass Cloudflare.
