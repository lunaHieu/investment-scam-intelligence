# V1-Core channel-contribution tooling V1

The builder and independent verifier prepare exactly one complete channel for a
future 300-group V1-Core release. They are predeclared and tested; no real
channel contribution has been created.

For every configured channel, the input must contain exactly 60 development
and 15 external-holdout groups. Partial contributions are rejected. Every row
must have all four unique group identifiers, immutable text/raw/review hashes,
raw Wayback provenance, timezone-aware collection time, human-reviewed
language, freshness and exclusion gates, `HIGH` evidence confidence, and
reconciled owner acceptance. Model fields are forbidden.

The language minimums are enforced independently for development and holdout.
The resulting contribution still cannot open a split, training, validation,
test, or scoring gate; all four channel contributions and the complete
balanced manifest remain mandatory.

The current 42 owner-accepted EDGAR records intentionally fail this builder:
the channel is short of 27 development and 6 holdout groups and the admission
fields identified by the V1 audit remain incomplete.
