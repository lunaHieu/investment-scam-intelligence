# Manual Source Owner Checklist V1

Date: 2026-10-20
Status: preparation only; no source is activated

Use this page when returning to the currently blocked DFPI, SSC and HNX
sources. The longer acquisition contract remains authoritative; this checklist
only makes the owner's actions and the handoff boundary explicit.

## What can be supplied now

### DFPI

- [ ] Use a normal browser session; do not bypass access controls.
- [ ] Prefer a first-party download/export. Otherwise save only the artifact
  legitimately displayed in the browser for internal research.
- [ ] Preserve the original bytes and original filename.
- [ ] Save at most 20 files for one submission under
  `D:\nckh 2026-2027\ISI_Data\raw\dfpi_crypto_scam_tracker\YYYY-MM-DD\`.
- [ ] Record the exact DFPI URL, access time, media type, byte size and rights
  basis for every file.
- [ ] Mark whether the artifact contains personal data.

DFPI complaint content remains `UNCERTAIN`, is not model input and is never an
automatic `CONFIRMED` label.

### SSC Vietnam

- [ ] First obtain an explicit official export/download with usable terms, or
  written permission for internal academic reuse.
- [ ] Retain the permission or terms evidence locally outside public Git.
- [ ] Do not save SSC records before that evidence passes independent QA.

### HNX

- [ ] First obtain an explicit official export/download with usable terms, or
  written permission for internal academic reuse.
- [ ] Retain the permission or terms evidence locally outside public Git.
- [ ] Do not save HNX records before that evidence passes independent QA.

An issuer profile may help identity reconciliation; it is not an automatic
`LEGITIMATE` label or a safety guarantee.

## Submission manifest

Copy
`registry/pilots/target_text_manual_acquisition_submission_template_v1.json`
to
`D:\nckh 2026-2027\ISI_Data\governance\target_text_corpus_v1\manual_submission_v1.json`.

Then replace every example value, remove `template_id` and `instructions`, and
set `status` to `PENDING_INDEPENDENT_INTAKE_QA`. Each file needs one manifest
item containing:

- unique item ID and source ID;
- exact official source URL and acquisition method;
- acquisition timestamp and original filename;
- path relative to `D:\nckh 2026-2027\ISI_Data\raw`;
- media type, byte size and lowercase SHA-256;
- rights-basis type, supporting URL/local evidence and a short factual note;
- redistribution and personal-data flags.

Do not put downloaded content, personal data or permission documents in the
public repository.

## What happens after handoff

1. AI verifies host allowlists, file presence, size, hash, acquisition method,
   rights evidence and personal-data flags.
2. A passing intake is registered without copying protected content into Git.
3. For SSC/HNX, Sampling Matrix V2 must be frozen before enumeration.
4. A separate hash-bound acquisition release must pass before any capture.
5. Official-reference prose remains evidence only; a distinct observed
   investment artifact is required for model text.
6. Grouping, primary review, blind second review, reconciliation and owner
   acceptance must all pass before corpus admission.

Until that sequence completes, these sources contribute zero training-ready
records.
