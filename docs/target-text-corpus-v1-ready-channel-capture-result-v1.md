# Ready-channel capture result V1

The exact-53 release stopped fail-closed after four requests. Three DEVELOPMENT
snapshots were captured and independently byte/hash verified. Row
`TTCV1_B3_AVAIL_009` returned 870 bytes, below the frozen 1,024-byte minimum;
it is preserved as a size-policy failure rather than silently admitted.
Forty-nine later rows were not attempted.

This was not HTTP 429 or a transport failure. The original release must not be
rerun. The three successful captures are immutable. Row `009` must not receive
an identical retry; it requires separate response-preserving diagnostic
tooling or an explicitly reviewed below-minimum policy. A later continuation
may cover only the 49 never-attempted rows without waiting 24 hours. Exact-text
extraction remains closed because capture QA is partial.
