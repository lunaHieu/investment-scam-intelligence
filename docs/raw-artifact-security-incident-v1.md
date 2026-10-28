# Raw Artifact Security Incident V1

Date: 2026-10-28

The V3 capture completed its network population (40 captured, 2 row-local
quarantines, 0 provider failures), but independent byte verification triggered
Microsoft Defender on `TTCV1_B3_AVAIL_021`. Defender identified
`Trojan:HTML/Cryxos.AGKB!MTB` (threat ID `2147957073`, severe) and quarantined
the file. Event IDs 1116/1117 record detection and successful quarantine.

The project must not disable Defender, add a filesystem exclusion, restore the
artifact, or continue opening raw HTML on this workstation. The capture report
is preserved with SHA-256
`6c694fa6ef1df1e6d344d443dfa2d99744f7e9e3b59cd792cdc1d60e918bf78d`.
Byte-level result QA, exact-text extraction, grouping, review and labeling are
closed until an approved isolated malware-analysis environment or a safe
source-side text-only acquisition method is selected.
