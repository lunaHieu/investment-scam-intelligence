# Ready-channel CDX canary result V1

The one-row metadata canary executed once after its frozen gate. It made one
request to `web.archive.org/cdx/search/cdx`, returned HTTP 200 JSON, and
preserved 286 raw bytes with SHA-256
`9d5a5996ebf4defa8016c08352f15268beabefe7bec60042be4d08196e1e09d8`.

The response contained two eligible HTML metadata rows for
`TTCV1_B3_AVAIL_002`; deterministic selection chose timestamp
`20201029053313`. Independent QA fully recomputed the raw-byte hash and
metadata. No archived page was downloaded, no live candidate domain was
opened, and no label was inferred.

The result authorizes preparation—not same-run execution—of an exact
unresolved-only CDX metadata release. Row 001 remains quarantined, row 002 is
resolved by the canary, and rows 003-070 form the separate 68-row release.
