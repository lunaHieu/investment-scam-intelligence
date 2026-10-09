# Target text corpus v1: blind second-review result

## Result

A reviewer with no inherited conversation history reviewed the 22 opaque records using only the frozen blind packet. The response contained:

- 4 `CONFIRMED` recommendations;
- 9 `LEGITIMATE` recommendations;
- 9 `UNCERTAIN` recommendations;
- 0 labels; and
- 0 training-eligible records.

Structural and scope QA passed. Coverage was exactly 22 unique blind IDs, all decisive recommendations passed every required assessment, and every uncertain recommendation named a non-pass assessment and an uncertainty reason.

## Blinding evidence

The packet omitted candidate IDs, source strata, group-review notes, primary recommendations, primary assessments, primary facts, primary rationales, and the primary summary. It also removed exact-text paths whose filenames encoded the original channel. The reviewer declared no access to the private map, primary result, model outputs, network, validation, or test artifacts.

The first structural QA was run against the reviewer's workspace response path and is preserved as a noncanonical-path attempt. The byte-identical response was then copied to the configured curated output path and passed the canonical structural QA.

## Reviewer caution

The blind reviewer independently noticed that two registration-evidence items carry the same `sec_number` and `source_record_id` while presenting different entity and host values. This is a source-data consistency warning, not a label, and must be resolved during reconciliation before either record can become eligible.

## Next gate

The second-review output is frozen before any private-map comparison. Reconciliation may now map opaque IDs back to candidates, enumerate agreements and disagreements, investigate the duplicated registration identity, and retain unresolved records as `UNCERTAIN`. No ground-truth or training gate opens automatically.
