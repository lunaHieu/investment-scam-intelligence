# Project Direction Plan R33

The bounded PBC05/PBC08 offline postmortem is complete. PBC05 failed during
PDF section extraction; the exact exception is unrecoverable from retained
artifacts. PBC08 was rejected by a parser `ValueError`; the exact guard is
unrecoverable because the response was not retained. Neither row is accepted
as evidence.

PBC06 repository metadata and PBC07 bounded documentation metadata are
registered by response hash and revision. This records provenance only: no
dataset rows or labels are admitted.

Parser diagnostics were improved and reviewed. PBC08 now has fixed guard
codes, and PBC05 uses a fixed five-code diagnostic set without exception text.
Focused coverage passed 9/9, current suite V9 passed 1156/1156, registry
validation passed, and implementation hashes match the remediation registry.

Next: perform owner review of the local change set. Any new source request for
PBC05/PBC08 requires a separately defined and authorized release; the completed
four-request execution is immutable and must not be repeated. Dataset
acquisition, evidence acceptance, labels, validation/test access and model
operations remain closed.
