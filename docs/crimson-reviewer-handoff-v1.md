# Crimson Reviewer Handoff V1

Date: 2026-10-20
Status: reviewer instructions only; no decision or label is created

## What this handoff is for

The Crimson branch contains 40 bounded review cases. AI-assisted preparation is
complete, but that is not human confirmation. One first review is recorded;
39 first reviews remain. Of the 21 cases requiring a blind second review, one
is ready and 20 remain closed until their first review is recorded.

Every case stays `training_eligible=NO` until review, reconciliation and owner
acceptance are complete.

## Immutable task files

Root:
`D:\nckh 2026-2027\ISI_Data\derived\crimson_human_review_packets_v2`

| File | Rows | Who may use it now | Purpose |
|---|---:|---|---|
| `first_review_pending_v2.jsonl` | 39 | Primary reviewer | Complete the first evidence review. |
| `blind_second_review_ready_v2.jsonl` | 1 | A genuinely independent second reviewer | Review without seeing AI or first-review decisions. |
| `blind_second_review_waiting_v2.jsonl` | 20 | Nobody yet | Dependency list only; wait for first review. |
| `official_reference_followup_v2.jsonl` | 15 | Primary reviewer or evidence collector | Manually check only the listed official-reference URLs. |

Do not edit these packet files. Record reviewer decisions through the existing
decision workflow so the immutable inputs remain reproducible.

## Safe review order

1. Assign the single ready blind-second task to a reviewer who cannot see the
   first-review record or AI suggestions.
2. Work through `first_review_pending_v2.jsonl` in `priority_rank` then
   `review_order` order.
3. For a row requiring a live follow-up, open only `official_reference_urls`.
   Never open `crimson_host`.
4. Record all required completion fields. Use `UNCLEAR` and
   `INSUFFICIENT_EVIDENCE` when the official artifact does not establish the
   relationship.
5. After a first review is formally recorded, regenerate and verify packets;
   only then may its waiting blind-second task become ready.

## Required fields and meanings

- `official_reference_checked`: which official artifacts were actually read;
  a URL being present is not proof that its content was verified.
- `identity_relationship`: `SAME_ENTITY`, `IMPERSONATION_SUSPECTED`,
  `UNRELATED`, or `UNCLEAR`.
- `evidence_assessment`: `WARNING_RELEVANT`, `REGISTRATION_RELEVANT`,
  `REFERENCE_NOT_APPLICABLE`, or `INSUFFICIENT_EVIDENCE`.
- `reviewer` and `reviewed_date`: truthful reviewer identity and review date.
- `review_notes`: short artifact-based rationale, including contradictions or
  missing evidence.

For blind second review, the reviewer must not receive primary decisions,
primary notes, AI identity suggestions or AI evidence suggestions.

## Decision rules

- Official warning wording can support a warning relationship but does not by
  itself create a model label.
- Registry membership, URL availability and lexical similarity are not labels.
- A failed or blocked official URL becomes insufficient evidence; it is not a
  negative finding.
- Disagreement between reviewers is preserved for reconciliation and defaults
  to uncertainty, never silently resolved by AI.
- AI may organize cited evidence and validate required fields. It must not
  impersonate either reviewer or invent a human decision.

## Completion gate

Crimson is not ready for corpus admission until all required first and blind
second reviews are recorded, the decision registry is independently verified,
disagreements are explicitly reconciled, and the owner accepts the resulting
recommendations. Until then, Crimson contributes zero training-ready rows.
