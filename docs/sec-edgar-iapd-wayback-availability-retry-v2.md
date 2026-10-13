# SEC EDGAR/IAPD Wayback availability retry V2

## Step name

Retry only unresolved availability rows after a fail-closed rate-limit stop.

## Meaning

The first execution resolved 45 of 115 rows and stopped safely after HTTP 429. This release preserves those 45 result objects unchanged and retries only 70 unresolved rows. The cooldown pace is at least 12 seconds per archive request, one attempt per unresolved row, with the same archive-only redirect and response guards.

No live candidate domain or archived page is requested. Retry errors remain unresolved, and availability remains routing metadata rather than a class label.

## Result

The endpoint remained rate-limited. V2 made two requests: one DNS-resolution error and one HTTP 429, after which the remaining 68 rows were not queried. All 45 resolved V1 results remain unchanged, leaving 26 available, 19 unavailable, and 70 unresolved. Further immediate retry is deferred until a later cooldown window.
