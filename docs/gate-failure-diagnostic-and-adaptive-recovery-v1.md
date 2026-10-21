# Gate Failure Diagnostic and Adaptive Recovery V1

Date: 2026-10-21
Status: active operational policy

This policy supplements every existing project gate. A gate may still fail
closed, but a failure is not complete merely because execution stopped. Every
material failure must be investigated, its impact bounded, and the least
restrictive compliant recovery path identified.

## Required failure report

For every material gate failure, record:

1. the observed symptom and immutable local evidence;
2. confirmed facts separately from hypotheses;
3. the most likely cause and viable alternative causes;
4. the exact affected records, stage and downstream dependencies;
5. whether any bytes, hashes, identities, partitions or prior results changed;
6. actions that are prohibited by a frozen contract or safety rule;
7. recovery options ranked by safety, time and evidentiary value;
8. work that can continue independently while the affected gate is closed;
9. the next decision time and the evidence needed to reopen the gate.

The project must not describe a remote HTTP status, timeout or missing artifact
as a proven root cause when the available evidence only establishes a symptom.
For example, HTTP 429 confirms server-side rate limiting, but does not by itself
identify whether the controlling quota is per IP, account, endpoint or service
load.

## Proportional closure

A failure closes only the smallest dependent scope. Unaffected immutable
results, separately authorized cohorts and offline work remain open. A small
unresolved subset should normally be quarantined instead of blocking a larger
independently verified population, provided an existing or separately frozen
contract permits that population to proceed.

No flexibility may change a committed hash, overwrite an artifact, silently
change cohort identity, contact a prohibited live candidate domain, infer a
label from availability, expose validation/test data, or bypass independent
review. These are safety and evidence invariants, not scheduling preferences.

## Adaptive recovery

Operational choices may be changed through a new, explicit and independently
verified release when the evidence supports the change. Examples include:

- separating availability retry from capture so one service symptom does not
  automatically block an otherwise authorized population;
- using bounded exponential backoff instead of an unconditional long cooldown;
- reducing request volume or pacing more conservatively;
- retrying only unresolved rows and preserving every resolved row unchanged;
- continuing offline QA, documentation and review-packet preparation;
- using another official or archive endpoint only after its terms, provenance,
  equivalence and release contract are reviewed and frozen.

A frozen release is never edited in place. If its cooldown or sequencing is too
conservative, the current run remains binding and the improvement is introduced
prospectively through a versioned amendment.

## Decision rule

The chosen response must be both compliant and proportionate. “Stop and wait”
is acceptable only when the evidence shows that immediate safe progress is not
available. Otherwise, the failure report must name and execute the independent
work or narrower recovery path that remains permitted.

For repeated failures, the next release must explain what changed relative to
the previous attempt. Repeating an identical retry schedule without a new
diagnostic justification is not an adequate recovery plan.

