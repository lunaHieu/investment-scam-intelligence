# Archive Rate-Limit Root-Cause Analysis V1

Date: 2026-10-22  
Scope: SEC EDGAR/IAPD Wayback availability V7-V10 and the pending one-row
capture retry

## Evidence

The repeated failure is not caused by the two candidate rows or by invalid URL
encoding. The project uses the documented
`https://archive.org/wayback/available?url=...&timestamp=...` form, DNS currently
resolves both archive hosts, and no HTTP proxy is configured.

The execution sequence shows a persistent archive-side throttle:

- V7 completed six earlier requests and received HTTP 429 on the seventh;
- V8 first encountered a local DNS-resolution failure, then received HTTP 429
  on the other unresolved row;
- V9 and V10 each received HTTP 429 on their first network request after a
  24-hour cooldown.

This pattern is consistent with a dynamic limit or block associated with the
client/network/endpoint rather than a one-minute burst. The exact server rule
cannot be reconstructed because the V7-V10 availability executor discarded
HTTP 429 headers, including any `Retry-After` value.

## Client-side deficiencies found

Internet Archive's current automated-access policy requires a descriptive
User-Agent containing the tool name, version, and—when an AI agent is
involved—the model name. It also requires clients to honor HTTP 429 and
`Retry-After`, and recommends exponential backoff.

The historical availability executor used
`ISI-Research/1.0 (academic archive availability)`. It identified the project
generically but omitted the AI model. It stopped correctly on HTTP 429, yet it
did not preserve response headers and therefore could not honor a server-
specified retry time. The fixed 24-hour schedule was an assumption rather than
a server-derived cooldown.

## Corrective action

The pending capture retry must use versioned V2 execution tooling instead of
mutating the hash-pinned V1 implementation. V2:

- sends `ISI-Research/2.0 (gpt-5;` plus the public project URL as the
  descriptive User-Agent;
- preserves `Retry-After`, `Date`, `Server`, `Content-Type`, and
  `X-Archive-Wayback-Runtime-Error`;
- makes exactly one attempt, stops on HTTP 429, and never overwrites output;
- retains the original release identity, candidate identity, cooldown, and
  independent result-verification contract.

No new archive request was made during this analysis. A future availability
V11 release must receive the same identification and diagnostic treatment; it
must not simply rerun the V10 client.

Official references:

- https://archive.org/developers/bots.html
- https://archive.org/developers/tutorial-get-snapshot-wayback.html
- https://github.com/internetarchive/wayback/issues/274
