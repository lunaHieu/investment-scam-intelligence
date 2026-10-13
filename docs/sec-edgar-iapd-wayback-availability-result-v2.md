# SEC EDGAR/IAPD Wayback availability result V2

## Step name

Execute and independently verify bounded archive availability queries.

## Meaning and result

V1 sent 51 archive-only availability requests before a fail-closed HTTP 429 stop. It resolved 45 rows: 26 with an available snapshot and 19 with no closest snapshot. Five requests timed out, one received 429, and 64 later rows were not queried.

After a frozen unresolved-only retry release, V2 sent two requests. The first encountered a DNS-resolution error and the second received HTTP 429; the remaining 68 were not queried. All 45 resolved V1 result objects were preserved unchanged. The cumulative result therefore remains 26 available, 19 unavailable, and 70 unresolved after 53 total archive-only requests.

Independent verification passed for both stages. Immediate further retry is blocked until a later cooldown window. No live candidate domain, archived HTML, artifact capture, label, validation/test partition, or model was accessed.
