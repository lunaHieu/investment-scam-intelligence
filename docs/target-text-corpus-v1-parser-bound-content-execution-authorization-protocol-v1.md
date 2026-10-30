# Parser-Bound Content Execution Authorization Protocol V1

This protocol is the next gate after commit `e80b2027`. It binds any future
live action to exactly eight parser-bound GET requests, the four allowlisted
authorities, the existing byte ceilings, no retry, no overwrite, no raw-body
retention and stop-after-first-failure behavior.

The protocol deliberately does not interpret a generic instruction such as
“continue with the next step” as permission to send network requests. The
owner authorization must explicitly name network execution and the exact
eight-resource scope. Until then, no execution amendment may be created and
the production capability remains unavailable.

After explicit authorization, a separate immutable amendment and independent
QA must be created and committed. Immediately before live execution the tree
must be clean, `HEAD` must equal `origin/main`, commit `e80b2027` must remain an
ancestor, focused and full tests must pass, and all planned output paths must
be absent. PBC05 remains subject to manual visual review after automated PDF
processing, so successful acquisition alone cannot admit evidence, labels or
training data.
