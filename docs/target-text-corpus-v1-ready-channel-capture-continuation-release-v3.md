# Ready-channel capture continuation release V3

V3 covers exactly 42 never-attempted rows. It preserves all response bytes,
quarantines HTTP 404/410 per row, and continues. HTTP 429, 5xx, transport errors
and unclassified provider failures stop execution. It uses 30-second pacing,
one attempt per snapshot, crash-safe journaling, no overwrite and no auto-resume.
