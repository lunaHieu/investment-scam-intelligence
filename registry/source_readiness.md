# Source Readiness Audit V1

**Audit date:** 2026-09-07  
**Purpose:** decide whether a source may enter the ISI pipeline, how it must be acquired, and what it must never be used to claim.

This audit authorizes no crawling and no model training. It defines the conditions that an adapter must satisfy before raw data is introduced.

| Source | Readiness | Acquisition decision | Permitted role | Non-negotiable interpretation |
| --- | --- | --- | --- | --- |
| Mendeley Investment-Related Deceptive Content V2 | `READY_FOR_MANUAL_DOWNLOAD` | Download the published CSV once; retain DOI/version, CC BY 4.0 license, original file name and SHA-256. | Text baseline; missing-modality and behavior ablation. | Its harmonized labels describe deceptive/suspicious investment-related content, not verified scam ground truth for every row. Never use in real-world Gold. |
| Crimson WWW 2025 | `READY_FOR_REPOSITORY_PIN` | Pin a commit SHA before download; retain repository license and dataset file checksum. Do not execute its crawler or login automation. | URL/OCR research branch, website case seeds. | Research-detected crypto investment-scam websites; not legal findings. Repository is GPL-3.0, so review redistribution implications before publishing derived bundled data/code. |
| IOSCO I-SCAN | `READY_FOR_MANUAL_EXPORT` | Use the portal's visible CSV export, archive the resulting file and export date. Do not bypass access controls or infer absence as legitimacy. | Entity/domain evidence and cross-checking. | Regulator alert/warning only; it is not proof of a conviction and the portal is not complete. |
| UBCKNN investor warnings | `READY_FOR_CURATED_CAPTURE` | Capture only individual public warning pages and their publication URL/date; preserve an HTML/PDF snapshot where allowed. | Vietnamese case/evidence curation. | A warning page is evidence. It is not automatically a positive solicitation artifact. |
| SEC IAPD / Form ADV | `READY_FOR_REFERENCE_DOWNLOAD` | Use public IAPD/SEC downloadable adviser snapshots; retain release date, URL and file checksum. | Legitimate entity reference and hard-negative verification. | Registration/reference status is not a content-safety label; entity legitimacy and individual content legitimacy remain distinct. |

## Verified source facts

- [Mendeley V2](https://data.mendeley.com/datasets/6wnd7jrt6z/2) was published on 13 May 2026, lists 16,202 records and 32 columns, and is licensed CC BY 4.0. Its description expressly limits the record labels to harmonized deceptive/suspicious behaviour.
- The [Crimson repository](https://github.com/pragseclab/Crimson) contains a JSON dataset of cryptocurrency investment-scam websites and source artifacts for a WWW 2025 paper. Its repository declares GPL-3.0.
- [IOSCO I-SCAN](https://www.iosco.org/i-scan/) aggregates voluntary member alerts and exposes a CSV export. IOSCO says the list is incomplete and that alert content remains the responsibility of the issuing member.
- [SEC IAPD](https://adviserinfo.sec.gov/) provides public adviser disclosure information. SEC documentation also identifies monthly and quarterly Form ADV data files for public use.
- The [UBCKNN warning index](https://ssc.gov.vn/webcenter/portal/ubck/pages_r/m/nhadautu/khuyencaonhadautu) includes public investor warnings about impersonation and unlicensed investment activity.

## Required manifest before ingestion

Every downloaded or captured source batch needs a manifest conforming to `schemas/source_manifest.schema.json` and must include:

1. Source ID and canonical URL.
2. Concrete source version or commit SHA, if available.
3. Download/capture timestamp in UTC.
4. License, terms, or public-use rationale reviewed at acquisition time.
5. Exact raw-label semantics.
6. SHA-256 of every immutable raw file and its storage path.

## Approval gate for the first adapters

1. Start with **Mendeley**: manual CSV download; manifest; read-only schema profiler.
2. Add **Crimson**: repository commit pin; JSON validator; no crawler execution.
3. Add **SEC IAPD** as a separate legitimate-reference adapter.
4. Treat IOSCO and UBCKNN as curated evidence adapters only, after the data model has been exercised on the first two sources.

No source is allowed to write directly into `data/curated` or `data/gold`. Every adapter writes immutable raw data plus a manifest first.
