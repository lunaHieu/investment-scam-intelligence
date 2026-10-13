# SEC EDGAR/IAPD Wayback availability execution release V1

## Step name

Release a rate-limited archive-only availability executor.

## Meaning

This release permits one availability request for each of the 115 frozen plan rows. Requests may contact only `archive.org` or `web.archive.org`, wait at least six seconds before every network operation, do not automatically follow redirects, and stop the remaining queue after HTTP 429. Every error remains unresolved rather than being converted to “no snapshot.”

The executor does not request a live candidate domain and does not download archived HTML. Availability is routing metadata, not evidence of either class. Capture, labeling, validation/test use, model scoring, and training remain blocked.
