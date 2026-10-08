# Target Text Corpus V1 Wayback capture result V2

After the five-day cooldown, the archive-only V2 executor attempted all 29 frozen snapshot URLs at a minimum ten-second interval. It made 29 requests without another HTTP 429 and captured 23 immutable HTML files. Six responses were rejected before writing because their bodies were below the frozen 1,024-byte minimum; those failures remain attached to their original candidates and were not replaced.

The 23 accepted captures total 1,558,271 bytes and are distributed as 4 regulator-linked, 5 CFTC RED-linked, 6 IAPD-linked, and 8 EDGAR-linked. The six rejected rows are distributed 1, 2, 2, and 1 respectively. Capture success and failure are acquisition outcomes, not binary labels.

Independent QA reconstructed the exact 29-row plan, checked that every candidate was attempted, matched the on-disk file set to the report, recalculated every accepted byte count and SHA-256, verified HTML content types and Wayback-only final URLs, and confirmed that failed rows wrote no files. All checks passed.

Exact text extraction is now allowed only for these 23 audited captures. The extraction stage must preserve the raw hashes, emit exact UTF-8 text hashes, enforce the minimum non-whitespace length, and run post-capture duplicate/group checks before any review or label decision. Live-domain access and binary labeling remain blocked.
