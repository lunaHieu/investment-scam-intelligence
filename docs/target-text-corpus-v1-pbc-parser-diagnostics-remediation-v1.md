# PBC Parser Diagnostic Remediation V1

This is a follow-on implementation note to the immutable offline postmortem.
It does not revise the PBC05/PBC08 outcomes or infer the original exception.

For future parser calls, PBC08 guards now map to bounded codes for a forbidden
dataset-like key, a missing/invalid commit list, a non-object commit entry, or
an invalid commit identifier. The rejected response and offending key/value
are not included in the code.

For future PBC05 extraction calls, the extractor emits a bounded code based on
the exception class and omits exception text. The lifecycle forwards that code
while retaining the existing stage, return code, and stdout/stderr hashes.
Unknown or unstructured failures continue to use the existing generic stage
diagnostic.

Focused synthetic coverage passed 6/6, and current test suite V9 passed
1156/1156. The registry validator also passes. The implementation authorizes
no network request, retry, evidence acceptance, dataset
download, labeling, validation/test access, or model operation. The next
technical gate is independent source review and explicit owner authorization
before considering any later acquisition action.
