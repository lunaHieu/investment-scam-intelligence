# Ready-channel capture continuation release V2

This release covers exactly 48 never-attempted rows from continuation plan V2. It does not retry rows `009` or `010`, and it cannot overwrite earlier captures.

The execution policy removes the repeated small-body bottleneck without weakening provider safety:

- every HTTP 200 response body is hashed and preserved before content classification;
- a row-local short or wrong-content response is quarantined and execution continues to the next row;
- HTTP errors, HTTP 429, and transport failures stop the branch immediately;
- a crash-safe partial journal is rewritten after every completed row and cannot be resumed automatically;
- candidate live domains, labeling, validation/test data, and model operations remain forbidden.

There is no fixed 24-hour delay. Execution must still occur in a separate invocation after independent release QA.
