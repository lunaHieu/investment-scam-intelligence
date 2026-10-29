# Target Text Corpus V1 Record-Free Endpoint Assessment Release V1

This release tests eight exact endpoints using HEAD only. Redirects are not
followed, response bodies are never read or retained, and only status/header
metadata may be recorded. It excludes every dataset landing/viewer page.

The assessment cannot authorize a subsequent GET by itself. Any endpoint that
appears suitable must still be placed in a new, separately verified content
release with an exact allowed content type and parser. Dataset acquisition,
author contact, labels, validation/test access and model operations remain
closed.
