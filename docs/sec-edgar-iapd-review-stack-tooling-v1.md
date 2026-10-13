# SEC EDGAR/IAPD review-stack tooling V1

## Step name

Predeclare bounded group review, primary evidence review, blind second review and
conservative reconciliation.

## Meaning

The manual group packet exposes only minimum-content records, exact text hashes,
contact indicators and frozen grouping/exclusion evidence. Reviewers may keep a
record provisionally distinct, merge groups with named positive evidence, route
an opened-cohort clone, confirm an automated exclusion, or leave the
relationship unresolved. Automated opened-cohort and holdout-collision
exclusions cannot be silently reinstated. No group decision creates a label.

The primary packet contains only group-approved representatives. It joins each
capture to the exact availability-plan row, conservative SEC/EDGAR-to-IAPD
offline identity review, normalized IAPD reference and full exact text.
`LEGITIMATE` is a recommendation only and requires all five checks to pass:
identity linkage, investment/advisory task relevance, capture chronology,
parking/repurpose screen and contradiction screen. Source membership alone is
explicitly insufficient; uncertainty in any check prevents an affirmative
recommendation.

The second-review packet carries the same evidence but omits all primary
recommendations, assessments, rationales and summaries. It contains only a hash
commitment to the frozen primary review. Its validator requires the reviewer to
declare that primary decisions and model predictions were not visible.

Reconciliation is deterministic: two `LEGITIMATE` recommendations produce only
a `LEGITIMATE` recommendation; any disagreement or any `UNCERTAIN` review is
reconciled to `UNCERTAIN`. Every record remains `ground_truth_status=UNCERTAIN`,
`label_created=false`, and `training_eligible=NO` until a separate owner
acceptance artifact is created after the real reviews are available.

## Current gate

The stack has been tested end-to-end using synthetic captured text and the
existing frozen offline reference inputs. No real group packet, primary review,
blind review, reconciliation or future label has been created. Owner acceptance
cannot be pre-granted for unseen future evidence.
