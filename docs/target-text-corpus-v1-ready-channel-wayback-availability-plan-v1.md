# Target-text corpus V1 ready-channel Wayback availability plan V1

## Step B3 and its meaning

B3 converts the immutable 70-row B2 provenance queue into an exact archive-only Wayback availability plan. It freezes who may be queried, in what order, for which historical target date, and through which endpoint. It does not execute the plan.

The plan preserves the B2 order and population:

- 25 `DEVELOPMENT` plus 10 `EXTERNAL_HOLDOUT` rows in `CONFIRMED_REGULATOR_LINKED_WEBSITE`;
- 25 `DEVELOPMENT` plus 10 `EXTERNAL_HOLDOUT` rows in `LEGITIMATE_REGISTER_LINKED_WEBSITE`;
- 70 unique candidate IDs, hosts, and normalized entities;
- zero development/holdout host or entity overlap.

All records remain `UNCERTAIN`, unlabeled, unscored, uncaptured, and ineligible for training.

## Historical target and network boundary

All 70 references were observed on 2026-10-03, so B3 fixes `20261003` as the availability target. This prevents a later execution date from silently changing the historical sampling target.

Every planned URL targets only `https://archive.org/wayback/available`. The candidate URL appears only as an encoded query parameter; B3 does not contact it. No archived page content is downloaded.

## Future execution requirements

B3 records but does not activate the following B4 requirements:

- a separately frozen and independently verified execution release;
- a descriptive project User-Agent;
- at least 60 seconds before every request;
- one logical attempt per candidate;
- a non-resumable partial journal reserved before network access;
- immediate stop on HTTP 429;
- preservation of `Retry-After` and archive diagnostic headers;
- no automatic resume, overwrite, live-domain request, archived-page download, label inference, scoring, or training.

## Commands

```powershell
.venv\Scripts\python.exe -m scripts.build_target_text_corpus_v1_ready_channel_wayback_availability_plan_v1 --config configs\target_text_corpus_v1_ready_channel_wayback_availability_plan_release_v1.json --verify-only
.venv\Scripts\python.exe -m scripts.build_target_text_corpus_v1_ready_channel_wayback_availability_plan_v1 --config configs\target_text_corpus_v1_ready_channel_wayback_availability_plan_release_v1.json
.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_ready_channel_wayback_availability_plan_v1 --config configs\target_text_corpus_v1_ready_channel_wayback_availability_plan_release_v1.json --output "D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\ready_channel_wayback_availability_plan_v1\independent_plan_qa_v1.json"
```

The output directory and its `.partial` sibling are no-overwrite artifacts. Only a passing independent QA permits B4 execution-release preparation; network execution remains closed.
