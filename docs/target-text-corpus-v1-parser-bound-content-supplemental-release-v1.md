# Parser-Bound Content Supplemental Release V1

This frozen preparation contains only PBC05 through PBC08. PBC01 through PBC04
already succeeded and must not be requested again. PBC05 may be attempted once
with PDF lifecycle V2; PBC06 through PBC08 are the three never-attempted
metadata resources.

A PBC05 parser failure is row-local and no longer blocks PBC06 through PBC08.
Transport errors and provider HTTP errors remain fail-closed for the whole
supplemental run. Raw response retention, retry, resume, dataset-file download,
candidate-domain access, evidence acceptance and all model operations remain
forbidden.

This release does not authorize network activity. A separately committed
executor, result verifier, independent QA and explicit owner execution
authorization are required before any supplemental request.
