# Dataset V1-Core source-capacity audit V1

The existing four-channel matrix is structurally valid but cannot be executed at scale without a source or channel amendment. This conclusion is based on hash-pinned local artifacts and a 2026-10-12 read-only review of current official source pages.

## Capacity result

| Channel | Current capacity | Planning reservoir | Result |
|---|---:|---:|---|
| Confirmed regulator-linked | 12,061 unique hosts | 469 | Reference capacity passes |
| Confirmed CFTC RED-linked | 12 unique hosts | 469 | Fails by 457 |
| Legitimate SEC IAPD-linked | 3,668 unique hosts | 235 | Reference capacity passes |
| Legitimate SEC EDGAR-linked | 33 unambiguous crosswalk rows; 20 independently approved | 134 | Crosswalk fails by at least 101 |

The CFTC website currently exposes an all-items list and individual detail pages, but no documented bulk file or public data API was identified. The frozen project contract does not authorize generic automated detail-page scraping, so the missing 457 candidates cannot be filled automatically.

SEC documents a `submissions.zip` bulk archive covering filing history for all filers. That is the correct next route for expanding the EDGAR identity universe. It requires a new versioned acquisition protocol, immutable raw hash, the existing private User-Agent safeguards, and the same strict independent identity review. The existing 0.8 name-match and 0.15 runner-up-margin thresholds must not be weakened merely to increase row count.

## Alternative channels requiring review

The DFPI Crypto Scam Tracker is a plausible confirmed-candidate seed because it publishes complaint narratives and associated websites. DFPI also states that reported losses are not verified. It therefore cannot create a `CONFIRMED` label automatically and needs independent official corroboration plus exact artifact linkage.

Official HNX and HOSE issuer profiles expose listing identity and, in some cases, an issuer website. SSC also publishes licensing and securities-business notices. These are plausible references for a Vietnamese legitimate channel, but listing or licensing is not proof that an artifact is safe, authentic, or uncompromised. A separate terms and source-role review is required before acquisition.

## Decision

No candidate wave is released. The next gate is to freeze and independently verify:

1. an SEC EDGAR `submissions.zip` bulk-universe protocol;
2. a DFPI corroborated-candidate source review;
3. an HNX/HOSE/SSC Vietnamese legitimate-reference source review.

If either alternative channel is adopted, the channel set and quotas must be frozen in Sampling Matrix V2 before candidate enumeration. This audit performs no official-data download, candidate-domain access, capture, labeling, model fitting, scoring, or partition opening.
