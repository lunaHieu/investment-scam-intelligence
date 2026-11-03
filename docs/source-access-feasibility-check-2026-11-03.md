# Source Access Feasibility Check — 2026-11-03

Status: exploratory, read-only assessment. No source data acquired, no rights established, and no dataset activated.

## Scope

This note advances the parallel source-access work in Project Direction Plan R42. It records what was reachable through official-source search/index pages and what still requires a direct artifact or permission. It is not a legal opinion, source license, review decision, or evidence-intake record.

No candidate domain was accessed. No message was sent to a third party. No source rows were enumerated into project data, no labels were created, and no model or validation/test data was touched.

## Findings

### FMA — Benefittrade and Banktrustcoin

- The official FMA search result for its “Entities falsely claiming New Zealand registration” list surfaced `Benefittrade (Imposter) | benefittrade.org/` and `Banktrustcoin | banktrustcoin.com/`, both dated 30 October 2025.
- The general FMA warnings page says its list is not exhaustive and entities may change names. The parent page exposes a dynamic search and a date-range CSV control.
- The project’s previously rate-limited exact list URL was not requested again. A web-tool attempt to activate the CSV control returned the parent page rather than a file; a direct read of the parent page from the local environment returned HTTP 403.
- A later attempt to access the FMA “Ask a question” service reached the REALMe FMA page, which displayed `403 Forbidden`; no login, registration, or submission was attempted.
- Therefore the new result is an official-site search/index lead only. It is not a retained official page or export, and does not close either primary-review task. Keep both cases `PENDING` / `UNCERTAIN`.

Official references:

- https://www.fma.govt.nz/library/warnings-and-alerts/entities-falsely-claiming-nz-registration
- https://www.fma.govt.nz/library/warnings-and-alerts/

### HNX — issuer-profile reference channel

- Official HNX search results expose issuer-profile and disclosure pages, so a public reference route exists.
- HNX also advertises separately licensed/copyrighted market-data packages and authorized distribution. That notice concerns those packages; it does not establish the rights status of the issuer-profile fields used by this project.
- No source-specific terms or written reuse basis for the planned issuer-profile extract were found in this check. Do not infer either permission or prohibition from the market-data notice. Keep the planned bulk reference extraction closed until the exact profile data and its reuse basis are documented.

Official references:

- https://vpdt.hnx.vn/vi-vn/m-tim-kiem-VXT.html
- https://www.hnx.vn/vi-vn/dich-vu-cctt/du-lieu-cung-cap-list.html

### SSC — investor-alert reference channel

- The official SSC Investor Alerts index is publicly discoverable. The web text reader returns a JavaScript-required shell for the index and an individual alert page; it does not provide a retained direct artifact in this check.
- No explicit reuse terms or official export for the planned alert-reference dataset were established. Do not enumerate or save SSC rows until an explicit export or written reuse basis is retained and independently checked.

Official reference:

- https://ssc.gov.vn/webcenter/portal/ssc/pages_r/m/investor/investoralerts?docType=TinBai&mucHienThi=190&selectedPage=2

### DFPI — Crypto Scam Tracker

- The current project record remains authoritative for the prior Cloudflare challenge and the no-bypass rule. This check made no new DFPI request and created no raw artifact.
- Intake still requires a lawful first-party export or an artifact the owner legitimately saves from a normal browser session. Treat complaint reports as unverified and `UNCERTAIN`; do not use them as automatic `CONFIRMED` labels.

Project reference:

- `docs/external-source-acquisition-2026-09-23.md`
- https://dfpi.ca.gov/consumers/crypto/crypto-scam-tracker/

## Decision and next actions

1. Keep the Crimson FMA tasks pending until a direct official page/export or user-supplied official copy can be retained and reviewed. Search snippets remain leads.
2. For SSC and HNX, obtain an explicit official export with usable terms or written permission for internal academic reuse of the exact fields. Keep sampling/enumeration closed until that evidence is independently checked.
3. For DFPI, use only the first-party/manual path already specified in `docs/manual-source-owner-checklist-v1.md`; do not bypass Cloudflare.
4. Once a lawful artifact or rights document exists, preserve the original bytes outside public Git, hash it, record exact source/access metadata and rights evidence, and run the existing intake QA before any downstream review.

## Verification boundary

This is a source-access feasibility note only. It does not update the frozen evidence/status JSONL outputs or their hashes. It does not satisfy the intake QA gate. No tests were run for this exploratory note, and no commit or push was made.
