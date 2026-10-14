# Raw Source Manifest Coverage Audit V1

## Step name

P2A — Verify every raw file covered by the checked-in source-manifest system.

## Meaning

This audit recomputes file hashes and compact structures for all supported
source manifests, then inventories the complete raw root without modifying any
file. The manifest scope currently covers the original Mendeley, Crimson,
IOSCO and SEC/IAPD sources plus selected official-warning, registered-homepage
and Wayback captures.

## Result

- 37 supported source manifests were found.
- All 37 referenced raw files exist.
- All 37 SHA-256 values match.
- No registered HTML artifact failed the basic HTML-structure check.
- The raw root contains 278 files totaling 1,640,058,635 bytes.
- 241 files are outside this specific source-manifest system.

`outside_source_manifest_scope_files` does **not** mean corrupt, unsafe, or
unregistered. Many later artifacts use acquisition-result, capture-result, or
benchmark registries instead of the original source-manifest schema. They must
be resolved by a separate cross-registry provenance audit before complete raw
coverage can be claimed.

Examples of work remaining include the CFTC captures, SEC EDGAR files, SEC bulk
archive, later matched-Wayback captures, the second Mendeley workbook, and the
V1 target-corpus snapshots. Empty DFPI and UBCKNN raw directories remain empty;
the audit does not infer any label or source absence claim from that fact.

## Gate

P2A passes only for registered source-manifest integrity. P2B must map the 241
remaining files to their other frozen registries and independently verify those
hashes. Training, labeling, validation/test opening, and model scoring remain
closed.
