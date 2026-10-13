# SEC EDGAR submissions bulk V1 storage amendment

## Step name

Replace full loose-file extraction with streamed logical extraction.

## Meaning

The verified archive is safe to inspect, but expanding 993,914 JSON members into almost one million loose files would add substantial NTFS metadata and repeated file-open cost. The existing crosswalk needs current filer identity fields, not every filing-history array.

This amendment keeps the original ZIP immutable and streams only primary `CIK##########.json` members into one versioned JSONL identity index containing `cik` and `name`. A full schema audit found 988,520 primary members, zero JSON errors, zero filename/JSON CIK mismatches, zero duplicate CIKs, and exactly one empty name. That single unusable identity row is excluded and counted without imputation, producing 988,519 expected rows. Historical submission fragments, filing histories, hosts, candidate URLs, labels, and model inputs are excluded. If an offline crosswalk later passes the frozen thresholds, only the selected evidence members may be materialized under a separate gate.

The change is a storage and processing optimization, not a relaxation of evidence rules. Candidate enumeration, shortlist materialization, labeling, validation/test, and model gates remain closed.
