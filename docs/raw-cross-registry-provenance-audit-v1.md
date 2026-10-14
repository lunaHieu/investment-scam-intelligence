# Raw cross-registry provenance audit V1

## Step and meaning

This is project-state step P2B. It tests whether each file under the raw-data root can be reached through an unbroken SHA-256 chain that starts in a JSON registry or configuration committed to Git. A file is not accepted merely because it exists or because a later dataset references it.

The audit is offline and read-only. It does not access live candidate domains, create or change labels, open model validation/test artifacts, or train or score a model. Transitive JSON reads are restricted to acquisition, capture, manifest, normalization, crosswalk, inventory, readiness, and artifact-audit documents.

## Frozen result

- Raw inventory: 278 files, 1,640,058,635 bytes.
- Verified through a Git-rooted hash chain: 191 files.
- No Git-rooted hash chain found: 87 files.
- Existing raw files with a conflicting pinned hash: 0.
- JSON roots inspected: 228; JSON documents parsed after safe transitive following: 261; parse failures: 0.
- Two missing claims point to the same historical `MATCHWB3_CONF_024__finrafx.com.html` artifact. Its already-registered independent capture audit classified it as `UNREADABLE_SECURITY_OR_IO_BLOCK`; it is absent from the raw inventory and remains excluded.

The 87 uncovered files are concentrated in historical external Wayback capture folders: 57 under `external_text_captures` and 30 under `external_text_matched_wayback_v2`. This result does not declare them corrupt. It means their local bytes are not yet connected to Git by the strict transitive hash rule used here.

## Decision

Status is `PASS_PARTIAL_PROVENANCE_GAPS_PRESERVED`. The 191 verified files remain usable only under their existing downstream gates. The 87 uncovered files must not be silently promoted; the next step is bounded provenance triage that locates pre-existing capture evidence and either registers a verifiable chain or explicitly quarantines the file. No provenance may be manufactured retroactively.

The authoritative machine-readable audit is stored outside Git at:

`D:\nckh 2026-2027\ISI_Data\derived\project_state_audit_v1\raw_cross_registry_provenance_audit_v1.json`

Its SHA-256 is `3cb325bd0a414cd348a8138c86e09528359b2cc1e097f8ee631619dae9b52f52`.

Three earlier diagnostic outputs with `invalid-*` in the same directory are non-authoritative. They were preserved rather than overwritten after tests exposed overly broad field pairing and transitive-read scope.
