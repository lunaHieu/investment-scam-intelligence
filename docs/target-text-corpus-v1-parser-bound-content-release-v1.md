# Parser-Bound Content Release V1 - Local Candidate

This local, uncommitted candidate binds each of eight previously HEAD-verified
resources to an exact content type, byte ceiling and parser. Only structured
metadata fields or named research-paper sections may survive parsing. Raw
responses are not retained.

Unexpected content types, oversized responses, forbidden dataset-record keys or
record-like fields cause immediate discard without retry. The ScamBench PDF is
limited to 24 pages, must pass PDF magic and visual review, and may exist only
under `tmp/pdfs` until deleted after extraction.

Execution remains explicitly closed because the user requested no commit or
push. The candidate can be tested locally but cannot perform network GET until
it is committed and independently QA-registered in a later authorized step.
PDF parsing is pinned to workspace dependency bundle `26.1025.11240`, which
contains pypdf 6.10.0 and pdfplumber 0.11.9; the project venv is not modified.

The local result verifier is exercised only with synthetic fixtures. It
recomputes resource order, lineage, byte ceilings, parser-specific field
allowlists, raw-body absence, summary counts and all downstream closed gates.
No real result file is created, and the verifier cannot authorize evidence,
dataset acquisition, labels or training.

The injected-transport harness exercises status, media-type, byte-limit,
redirect, parser, append-only journal and stop-after-first-failure behavior
using in-memory synthetic responses. The harness has no HTTP client and the
command-line executor remains locked to `--verify-only` while this candidate is
uncommitted.

An eight-resource end-to-end dry run uses only in-memory synthetic responses.
It traverses the injected transport, all eight parsers, a ten-event temporary
journal, temporary result assembly and the independent result verifier. The
temporary directory is destroyed before the dry run returns, so it cannot be
mistaken for project evidence or a completed acquisition.

The adversarial matrix injects one distinct failure into each of the eight
resources. Every honest failure report must remain independently verifiable,
all later resources must be skipped, and a tampered report that changes the
failure to `SUCCESS` must be rejected. Each scenario uses its own temporary
directory and retains neither journals nor results.

The production HTTP transport uses a pinned descriptive User-Agent, a
30-second timeout, 64 KiB bounded reads, no automatic redirects and no retry.
Only the single immutable Hugging Face documentation redirect may be followed.
The real opener requires an in-process capability that can only be minted by a
successful execution preflight; the current uncommitted release cannot mint
that capability. Transport mechanics are tested only with injected fake
openers.

The production orchestrator reserves the partial path exclusively before any
transport call, fsyncs an atomic JSON checkpoint after every resource, stops
after the first failure, and writes the complete candidate back to the partial
path. Only an independently verified candidate is atomically renamed to the
final path. A verifier failure preserves the partial and creates no final;
automatic resume is forbidden. Live orchestration remains blocked before the
real opener while the execution preflight is closed.

PBC05 has a dedicated PDF lifecycle. It writes the response only inside a
unique directory under `tmp/pdfs`, verifies the byte hash and PDF structure,
extracts only matched research-method sections, renders every page at 100 DPI,
checks PNG structure and page cardinality, and deletes the PDF plus rendered
pages on both success and failure. Automated processing cannot satisfy the
visual-review gate: the retained status remains `PENDING_REQUIRED`, and
evidence acceptance remains closed.

The execution-readiness audit independently recomputes the complete local file
set, every QA hash, Git lineage, release-input hashes, exact authority set,
bundled PDF dependency versions, planned-output absence and the network-call
surface. It requires `urllib.request` and `build_opener` to appear only in the
capability-gated HTTP transport. Passing this audit means only that the stack is
ready for commit review; execution, acquisition and training remain closed.
After explicit owner authorization, the same audit accepts either the exact
23-file pre-commit set or those same 23 files tracked in a committed state; it
does not treat staging or any mixed state as valid.
During the authorized commit-to-push transition, Git lineage may be equal to
`origin/main` or exactly one commit ahead with zero commits behind; divergence
or a longer unpublished chain remains invalid.

The pre-commit review also enforces outcome-specific result invariants:
successful rows cannot retain diagnostics; parser rejections require HTTP 200,
a response identity and a diagnostic; HTTP errors cannot claim status 200;
transport errors cannot retain response metadata; and PDF extracted identity
must match the original response hash and byte count.
