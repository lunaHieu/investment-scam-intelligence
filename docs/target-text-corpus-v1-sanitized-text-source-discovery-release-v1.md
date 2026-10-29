# Sanitized Text Source Discovery Release V1

This release freezes exactly 12 unique search queries across English confirmed,
English legitimate, Vietnamese confirmed, Vietnamese legitimate and multilingual
strata. At most 20 sources may be shortlisted.

Execution may inspect search metadata and first-party dataset, documentation,
terms, paper-abstract or dataset-card pages. It cannot download source files,
visit candidate domains, retain raw HTML, follow dataset-contained links, create
labels or run a model. The output is immutable and may be created only after the
release verifier and independent QA pass.
