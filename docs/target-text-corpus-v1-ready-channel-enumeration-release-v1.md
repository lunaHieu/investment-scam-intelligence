# B1 — Ready-channel enumeration release V1

Date: 2026-10-23

B1 starts the capacity-expansion workstream with only the two channels whose
existing reference pools passed the source-capacity gate:

- regulator-linked `CONFIRMED`;
- IAPD/register-linked `LEGITIMATE`.

The first wave is fixed at 25 development and 10 external-holdout candidates
per channel, for 70 candidates total. Development and holdout have distinct
deterministic namespaces.

Before capacity is credited, the preflight excludes every host present in the
opened external index, the earlier four-channel pilot queue, or the complete
115-row SEC/IAPD availability population. It also rejects cross-channel host
collisions and normalized entity collisions across the two target strata.

B1 does not select the final 70 candidates. It proves that sufficient eligible
reference capacity remains after all frozen exclusions and authorizes B2 to
materialize the deterministic queue. B1 performs no network request, Wayback
query, candidate-domain access, capture, label creation, model scoring or
training.
