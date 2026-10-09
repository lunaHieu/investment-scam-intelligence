# Target text corpus v1: primary case-and-artifact review

## Purpose

This gate reviews the 22 minimum-content captures against their frozen local official evidence. It records a conservative **primary recommendation**, not a ground-truth label.

## Decision rules

- `CONFIRMED` requires investment-related captured content, specific identity/domain linkage, official warning evidence, consistent chronology, and no unresolved repurpose, parking, or contradiction signal.
- `LEGITIMATE` requires investment-related captured content, specific linkage to an active official registration record, consistent chronology, and no unresolved clone, repurpose, parking, or contradiction signal. Registry membership alone is insufficient.
- `UNCERTAIN` is mandatory when identity, relevance, chronology, affiliation, repurpose, parking, or contradiction cannot be resolved from the frozen evidence.

The candidate source stratum is never treated as ground truth. For the SEC EDGAR channel, the EDGAR-to-IAPD shortlist is supporting provenance only; the captured artifact must independently align with the IAPD entity and host.

## Isolation and safety

The packet is built only from pinned local inputs. The reviewer receives no model prediction or score and performs no live-domain or network access. Every record remains `ground_truth_status = UNCERTAIN`, `label_created = false`, and `training_eligible = NO` after this gate.

## Exit gate

All 22 records must have the five required assessments, at least two concrete supporting facts, and a substantive rationale. Any decisive recommendation must pass every assessment. A passing structural QA only releases a blind independent second review; reconciliation and owner acceptance remain mandatory before any label or training eligibility can change.
