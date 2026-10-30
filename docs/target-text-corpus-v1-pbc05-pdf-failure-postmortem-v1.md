# PBC05 PDF Failure Postmortem V1

PBC05 returned HTTP 200 with `application/pdf`, 1,906,912 bytes and a stable
SHA-256, then failed inside the bounded PDF subprocess chain. The confirmed
failure class is a non-zero subprocess exit. V1 cannot distinguish whether it
occurred in `pdfinfo`, section extraction or `pdftoppm` rendering because it
retained only `CalledProcessError` and correctly deleted the raw PDF, rendered
pages, stdout and stderr.

This is a diagnostic-observability defect, not evidence that the source is
invalid or malicious. It does not justify silently retrying the same release.
The current result remains immutable and PBC05 remains unaccepted.

PDF lifecycle V2 records only stage, return code, byte counts and hashes of
stdout/stderr. It retains no subprocess text and no raw PDF. A supplemental
release may retry PBC05 once with V2 diagnostics and then continue to the three
never-attempted metadata resources after a row-local parser failure. Provider
or transport failures still stop the complete run.
