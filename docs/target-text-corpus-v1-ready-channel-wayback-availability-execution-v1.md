# Target-text corpus V1 ready-channel Wayback availability execution V1

## Step B4 and its meaning

B4 freezes the crash-safe executor and concrete execution contract for B3's exact 70-row availability plan. It makes the future network run reproducible and recoverable without executing that run during preparation.

The release remains network-closed at freeze time. A later execution must satisfy both:

1. the absolute `not_before` floor; and
2. at least 24 hours after the actual A1 CDX report timestamp.

The executor refuses to run if A1 is absent, still has a `.partial` journal, fails independent result QA, preserves an HTTP 429/error, or makes the dynamic cooldown later than the fixed floor.

## Crash and rate-limit behavior

Before the first network call, the executor exclusively creates a non-resumable `.partial` journal. It checkpoints after every logical attempt. A process crash preserves that journal and blocks automatic rerun. Controlled HTTP, transport, payload, or parsing errors stop the remaining population; HTTP 429 additionally preserves `Retry-After` and the configured archive diagnostic headers.

Future execution is limited to:

- exactly the 70 B3 identities in their frozen order;
- `archive.org` and `web.archive.org` only;
- at least 60 seconds before every HTTP request, including redirects;
- one logical attempt per candidate;
- at most three archive-only redirects;
- JSON responses no larger than 2 MiB;
- a descriptive project User-Agent.

No candidate live-domain access, archived-page download, artifact capture, label inference, validation/test opening, model scoring, or training is permitted.

## Preparation commands

```powershell
.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1 --release configs\target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1.json --output "D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_availability_plan_v1\independent_execution_release_qa_v1.json"
.venv\Scripts\python.exe -m scripts.execute_target_text_corpus_v1_ready_channel_wayback_availability_v1 --release configs\target_text_corpus_v1_ready_channel_wayback_availability_execution_release_v1.json --release-qa "D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_availability_plan_v1\independent_execution_release_qa_v1.json" --verify-only
```

The non-`--verify-only` command is reserved for a later gate. At 60 seconds per candidate, a complete 70-row run requires at least about 70 minutes, excluding redirects and response time.
