# Target Text Corpus V1 Wayback availability result V2

Wayback availability is fully resolved for the frozen 40-candidate queue. V1 made ten requests and stopped on HTTP 429; V2 retained its nine resolved rows unchanged, retried only the 31 unresolved rows at a six-second interval, and completed without another rate-limit response. Across both runs there were 41 availability requests, zero live candidate-domain requests, and zero archived-page downloads.

Twenty-nine candidates have an archive snapshot and eleven do not. Availability by channel is 5/10 regulator-linked, 7/10 CFTC RED-linked, 8/10 IAPD-linked, and 9/10 EDGAR-linked. These differences are capture availability, not evidence for a binary label, and no quota is reallocated across channels.

Independent QA matched all 40 IDs and identity fields back to the frozen queue, proved that only V1 error rows were retried, verified the nine reused results byte-for-byte at the JSON-record level, and accepted only HTTPS-normalized `web.archive.org` snapshot URLs with stored HTTP status 200. All checks passed.

This milestone releases construction of a capture plan for the exact 29 available snapshots. It does not yet authorize downloading archived HTML, opening a live candidate domain, labeling a candidate, or using any row for model development.
