# Target Text Corpus V1 channel terms review

Status: **two replacement channel protocols registered; candidate acquisition has not started**.

This review replaces the two blocked channel designs identified by the pre-acquisition inventory. It registers source semantics, access constraints, capture boundaries, and claim limits before any candidate is enumerated or captured. It is an operational research review, not a legal opinion.

## Why the original designs were replaced

The original corroborated-case-seed channel lacked a single official reference and capture contract. The original legitimate post/message channel depended on a social-platform source that had not been registered or terms-reviewed.

The replacement keeps both classes in the same `WEBSITE_SNAPSHOT` modality and uses different official reference channels:

| Target status | Existing channel | Replacement/second channel |
|---|---|---|
| `CONFIRMED` | IOSCO/FCA/UBCKNN regulator-linked archived websites | CFTC RED-linked archived websites |
| `LEGITIMATE` | SEC IAPD-linked archived adviser websites | SEC EDGAR-linked archived issuer/IR websites |

This yields two registered channel protocols per target status while avoiding social-platform scraping and message-account ownership ambiguity.

## CFTC RED List

The CFTC RED List is a regulator warning/reference source. CFTC says a listed foreign entity appears to act in a capacity requiring registration but is not registered. CFTC also states that inclusion does not mean the CFTC or a court concluded that a legal violation occurred.

CFTC's web policy says government information on its website is public domain and may be copied and distributed with appropriate acknowledgement. Third-party contributed or licensed items may remain protected.

Operational policy:

- initial reference acquisition is manual or through an explicit official download;
- no generic automated scraper is authorized by this review;
- exact entity/domain linkage and a separate observed solicitation artifact are required;
- RED inclusion cannot create a final label by itself; and
- warning text is evidence only and cannot be model input.

## SEC EDGAR

SEC EDGAR is an official entity, submission, and filing reference. It is not a content-safety label. An SEC identifier or filing cannot by itself prove that a domain or communication is legitimate.

SEC documents programmatic API and bulk-data access, subject to its website Privacy and Security Policy. The current official policy limits aggregate automated requests to no more than ten per second and may restrict unclassified bots or excessive access.

Operational policy:

- only documented SEC APIs or bulk archives may be used;
- the project cap is one request per second;
- a truthful project contact identity must be configured before any request;
- immutable raw responses and hashes are required;
- filing text and metadata cannot be predicted content or model features; and
- exact filer/domain identity plus contradiction review is required.

Because contact identity has not yet been configured, scripted SEC access remains blocked.

## Artifact capture contract

Both replacement channels use archived website HTML. Only `archive.org` and `web.archive.org` may be contacted by the future capture step. Live candidate domains, external redirects, overwrites, and redistribution are prohibited. All raw captures require an immutable path and SHA-256.

The project cap is one request per second, and acquisition must stop on HTTP 429 or any policy change. Source and archive terms continue to apply.

## Gate result

Channel protocol registration passes at two channels per target status. This does not open candidate enumeration, capture, labeling, training, validation, test, or deployment.

The next gate is to freeze a balanced 20+20 schema/review pilot candidate-enumeration protocol. Actual CFTC enumeration waits for a manual/official-download artifact, and SEC enumeration waits for a truthful User-Agent contact identity.
