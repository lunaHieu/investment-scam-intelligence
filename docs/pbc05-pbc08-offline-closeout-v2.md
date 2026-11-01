# PBC05/PBC08 Offline Closeout V2

Date: 2026-11-01
Status: result history reconciled offline; exact historic causes remain unknown.

## What the pinned results actually show

This closeout compares three separately hash-pinned result snapshots. They do
not represent three attempts for every row. The first result stopped after
PBC05 failed, so PBC08 was recorded as `SKIPPED_AFTER_FAILURE` and had no HTTP
response in that snapshot.

| Result artifact | PBC05 | PBC08 | Other rows |
|---|---|---|---|
| `target_text_corpus_v1_parser_bound_content_result_v1.json` (`987930b7…`) | HTTP 200 PDF; `PDF_LIFECYCLE_CALLEDPROCESSERROR`; exact subprocess stage unavailable. | `SKIPPED_AFTER_FAILURE`; `EARLIER_RESOURCE_FAILED`; zero response bytes. This is not a PBC08 attempt. | Earlier eight-resource result snapshot; four succeeded before PBC05 failed, and three later rows were skipped. |
| `target_text_corpus_v1_parser_bound_content_supplemental_result_v1.json` (`e4b35161…`) | HTTP 200 PDF; `SECTION_EXTRACTION`, return code 1, stdout 0 bytes, stderr 759 bytes, SHA-256 `7010f9e7…`. | HTTP 200 JSON; generic `PARSER_REJECTED_VALUEERROR`; offending response not retained. | PBC06 metadata and PBC07 bounded documentation parsing succeeded as provenance only. |
| `target_text_corpus_v1_parser_bound_content_diagnostic_result_v1.json` (`5fcddbb8…`) with independent QA | HTTP 200 PDF; `SECTION_EXTRACTION`, return code 1, stdout 0 bytes, stderr 710 bytes, SHA-256 `daa76cb3…`. | HTTP 200 JSON; `PARSER_REJECTED_FORBIDDEN_DATASET_KEY_PRESENT`. | Latest exact two-row diagnostic result. |

Thus PBC05 has three recorded attempts across these artifacts, including two
instrumented attempts. The two instrumented PBC05 results have the same
response SHA-256
`11be0eb75a64c1b61ac24fe1e45489bd497246409d834fc1da3869edc002287b` and
1,906,912 response bytes, but different stderr byte counts and hashes because
they are different executions/tool states. The raw PDF and stderr text were
deleted; those hashes cannot reconstruct them.

PBC08 has **two** actual attempts in the supplemental and latest diagnostic
results. They refer to the same 2,781-byte response hash
`45e80332128724f860215f709ab938d386d4f63ee1ea42bdf5b32598c5261111`.
The supplemental parser reported only `ValueError`; the latest instrumented
result narrows that attempt to the configured forbidden-dataset-key guard.
The exact key, JSON path, and value were not retained.

## Confirmed facts

### PBC05

- The source returned HTTP 200 with `application/pdf` and the response hash
  shown above.
- The two instrumented runs failed in `SECTION_EXTRACTION` with return code 1
  and no stdout. Their stderr lengths/hashes are distinct and separately
  pinned.
- Offline code-path analysis found a normal handled extractor exception would
  emit a sanitized structured diagnostic and exit with code 2. The observed
  return-code/stdout pair does not match that normal handled path. It narrows
  the boundary to a failure before that handler completed or abnormal child
  termination; it does not prove which event occurred.
- The raw PDF, rendered pages, stdout and stderr text are absent. The exact
  exception, failing system call, and cause cannot be recovered offline.

### PBC08

- The two actual requests returned HTTP 200 with JSON content type and the
  same response hash.
- The latest diagnostic result confirms that a configured
  forbidden-dataset-key guard fired. The parser checks configured keys
  recursively and case-insensitively.
- The original JSON and offending key/path/value are not retained. The result
  cannot distinguish which configured key caused rejection or what other
  metadata/schema checks would have returned afterward.

### PBC06/PBC07

- PBC06 registered repository metadata at revision
  `a90e2bd7e8df2376939658075ba8094dcee488ad`, including a declared
  `cc-by-4.0` license and file names. This is not a legal review, content
  inspection, or data admission.
- PBC07 retained one bounded documentation section about train/test splits.
  It does not establish the actual row split, schema, label quality, or sample
  contents.
- Neither row has been admitted to the usable dataset. No dataset rows or
  labels were created.

## What cannot be inferred

- The precise PBC05 exception or whether the document, a tool, a system
  dependency, or an abnormal child exit caused it.
- The exact PBC08 forbidden key or any discarded response field.
- Whether either response was malicious or malware-free. No malware scan result
  is retained; absence of a detection is not evidence of a clean artifact.
- Dataset quality, representativeness, row count, label correctness, or
  fitness for training from repository identity, file names, or a README.
- Any `SCAM`/`LEGITIMATE` label from parser outcomes, source availability,
  registry membership, or SEC/IAPD identity evidence.

## Resolution and next action

The offline diagnosis is complete. Historical result files and previous
postmortems remain unchanged. The earlier exact-two-row diagnostic release is
exhausted and may not be rerun. The current candidate-preflight V1 is a
structural check only; it reports that no actual release or network execution
is authorized. This closeout creates no source request.

If the owner later chooses to revisit these sources, that requires a new,
separately versioned exact two-row release, unique output paths, independent
release QA, and scoped execution authorization. Do not reuse or rewrite the
old results. If a future authorized artifact scan detects malware, stop
processing that artifact and quarantine it. This project has no retained
finding that malware was detected or excluded.

No validation/test data was opened, no model was trained or scored, no
candidate domain was accessed, and no label or training eligibility was
created by this closeout.

Machine-readable evidence: `registry/analyses/pbc05_pbc08_offline_closeout_v2.json`.
