# Reproducibility current state V40

V40 supersedes V39 after the exact-68 CDX bulk metadata execution completed
and the exact eligible capture plan was independently verified.

The metadata stage resolved all 69 attempted rows (`002`-`070`). Fifty-three
have eligible snapshots and sixteen are valid empty metadata. The immutable
capture plan includes every and only eligible row in source order: 37
DEVELOPMENT and 16 EXTERNAL_HOLDOUT. Row `001` remains quarantined.

No page capture occurred in this stage. The next gate is preparation and
independent verification of a separate exact-53 capture execution release.
Candidate live domains, labels, validation/test, scoring and training remain
closed.
