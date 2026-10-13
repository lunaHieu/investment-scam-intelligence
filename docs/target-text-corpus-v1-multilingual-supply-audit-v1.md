# Target Text Corpus V1 multilingual supply audit

## Step name

Audit verified Vietnamese and other non-English supply in the four frozen acquisition channels.

## Meaning

Language coverage is a data requirement, not a model feature or a guess from geography. A candidate contributes language supply only after an archived artifact has immutable visible text, an exact text SHA-256, and a human-reviewed language decision. Domain suffix, entity country, regulator jurisdiction, and reference-page language are not accepted as artifact-language evidence.

The offline audit inspected 16,504 current metadata rows across the four channels. None contains the required observed artifact text, text hash, and reviewed language fields. All 16,504 therefore route to `UNKNOWN`: zero verified Vietnamese rows and zero verified other-non-English rows. This does not mean the sites are English; it means the current reference metadata cannot establish their language.

## Decision

The multilingual supply gate fails closed for both target statuses. No quota is waived, and no candidate release, capture, label, validation/test access, or model operation is authorized by this audit.

The next data-design gate is to register and terms-review a Vietnamese legitimate-reference path and a balanced confirmed-language path. Only fresh archived artifacts that pass capture, text hashing, grouping, and human language review may satisfy the frozen quota.
