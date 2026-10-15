# Raw cross-registry provenance audit V2

## Step and meaning

This is project-state step P2E. After the P2D anchor was committed and pushed, the audit re-enumerated and re-hashed the complete raw directory from scratch. It did not infer completion from the prior triage or anchor.

## Frozen result

- Existing raw files: 278.
- Existing raw bytes: 1,640,058,635.
- Files with a Git-rooted transitive SHA-256 chain: 278/278.
- Existing files without a chain: 0.
- Existing files with a conflicting hash: 0.
- JSON parse failures: 0.
- Files promoted: 0.

Three missing claims refer to two absent historical files, not to files in the current raw inventory:

- `MATCHWB2_CONF_033__luctra.net.html`: the historical independent audit recorded `MISSING_AFTER_CAPTURE_POSSIBLE_SECURITY_QUARANTINE`.
- `MATCHWB3_CONF_024__finrafx.com.html`: two historical records refer to the same file, and the independent audit recorded `UNREADABLE_SECURITY_OR_IO_BLOCK`.

These artifacts remain absent and excluded. The audit does not bypass endpoint protection, recreate the bytes, or treat the missing claims as current raw files.

## Decision

Status is `PASS_COMPLETE_EXISTING_RAW_PROVENANCE`. This closes the integrity/provenance gap for every raw file currently stored under the project raw root. It does not open labeling, model training, validation, test, or benchmark scoring. The next project-state action is to update the state ledger and move to the next independent data-readiness branch while the SEC/IAPD V4 cooldown remains binding.

Authoritative output:

`D:\nckh 2026-2027\ISI_Data\derived\project_state_audit_v1\raw_cross_registry_provenance_audit_v2.json`

SHA-256: `6470aa8b876343b55b4844c75925ac069cf2b6f7d671ad6c89f4c26b40fdc587`.
