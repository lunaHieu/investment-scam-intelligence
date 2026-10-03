# Target Text Corpus V1 Wayback availability plan V1

Status: **archive-only availability query authorized; archived-page capture and labels blocked**.

This gate fixes the exact input population and network behavior before any availability request. The input is the hash-pinned 40-row candidate queue: ten candidates from each of the four provenance channels. Every row must still be `UNCERTAIN`, unlabeled, unqueried, and ineligible for training.

The query sends each candidate URL only as an encoded parameter to `https://archive.org/wayback/available`, using the target date `20261003`. It does not request the candidate URL itself. HTTPS redirects are handled manually and accepted only when the destination remains `archive.org` or `web.archive.org`. The process uses one attempt per candidate, at least 1.1 seconds between requests, and stops the remaining queue after HTTP 429.

The output is an availability report, not a website capture. It may contain a Wayback snapshot timestamp and URL, but it downloads no archived HTML. Errors remain errors and cannot be converted into “no snapshot.” An existing output path is never overwritten.

Capture planning stays blocked unless all 40 candidates receive a resolved availability result. Even after successful availability querying, a separate plan must select and hash-register the exact snapshot URLs before archived pages can be downloaded. Live candidate-domain access, binary labeling, model scoring, training, validation, and test access remain prohibited.
