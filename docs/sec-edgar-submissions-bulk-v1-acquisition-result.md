# SEC EDGAR submissions bulk V1 acquisition result

## Step name

Acquire and independently verify the official SEC submissions bulk archive.

## Meaning

The project now has a versioned, immutable all-filer SEC reference archive at `D:\nckh 2026-2027\ISI_Data\raw\sec_edgar_bulk\submissions_2026-10-12.zip`. Its independently recomputed SHA-256 is `39c288191b846ccc1e2fc79b5da95c3d53d26e29f9c9b3373be2aa6c1e569e3f` and its size is 1,568,623,659 bytes.

The ZIP contains 993,915 members: 993,914 JSON files and one TXT file. Its uncompressed member total is 5,754,848,183 bytes. A separate verification pass recomputed the archive hash and size, reopened the central directory, and repeated the full CRC test. The public manifest hash is `83ca3471968f91d5783aaa4e79e154d5157dc900ea21b4afdf55feda63dd800a`.

This archive is reference data only. It does not prove that a filer website is legitimate, does not create a candidate or label, and does not authorize extraction yet. The next gate must define a JSON-only, non-overwriting staged extraction and rebuild the EDGAR-to-IAPD identity crosswalk without lowering the frozen name-match or runner-up-margin thresholds.
