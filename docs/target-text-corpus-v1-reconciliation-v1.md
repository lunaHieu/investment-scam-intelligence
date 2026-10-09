# Target text corpus v1: primary/second-review reconciliation

This gate compares the two frozen reviews only after the blind second-review result is registered. Twenty recommendations agree. Two disagree: the second reviewer marked SEI and Commonwealth/CIM uncertain because it asserted that their SEC identifiers collided.

Independent recomputation from the frozen packet disproves that assertion. SEI has `801-24593 / 105146`; Commonwealth/CIM has `801-47108 / 106292`; all 14 registration composite keys are unique. Both disputed artifacts also have matching registered names or aliases, exact official hosts, investment content, approved registrations, and no independent repurpose contradiction. The reconciliation therefore retains the primary `LEGITIMATE` recommendation for both and records the second-review issue as a factual error.

The reconciled distribution is expected to be 4 `CONFIRMED`, 11 `LEGITIMATE`, and 7 `UNCERTAIN`. All remain non-label recommendations with `ground_truth_status = UNCERTAIN` and `training_eligible = NO`. Owner acceptance is the next gate; reconciliation alone cannot materialize labels.
