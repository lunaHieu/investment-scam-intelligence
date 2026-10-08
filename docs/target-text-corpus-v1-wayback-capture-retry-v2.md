# Target Text Corpus V1 Wayback capture retry V2

The first archived-page capture attempt on 03 October 2026 received HTTP 429 on its first request. The executor stopped immediately, recorded one failure and 28 untouched rows, and wrote zero raw capture files. That report is immutable and hash-registered.

After more than 24 hours of cooldown, V2 is authorized to retry only the 29 unresolved rows. It uses the same frozen snapshot URLs and target paths, one attempt per candidate, at least ten seconds between requests, and a 45-second timeout. It stops all subsequent work on another HTTP 429, preserves every error, follows redirects only within Wayback, and writes files exclusively with create-new semantics.

This gate permits the archived-page retry only. Text extraction remains blocked until every resulting file path, byte count, and SHA-256 has passed an independent audit. Live candidate domains, labels, model operations, validation, and test access remain prohibited.
