# Reproducibility guide — current project state V3

Snapshot date: 2026-10-16 (Asia/Saigon).

## Tên bước và ý nghĩa

**P8R2: chuyển điểm điều hướng sang ledger V5.** Guide V3 giữ các snapshot cũ
bất biến nhưng thay hướng dẫn V2 đã lỗi thời sau lần chạy SEC/IAPD V4. Đây chỉ
là bản đồ tái lập và kiểm soát gate; nó không tải dữ liệu, tạo quyết định con
người, tạo nhãn, mở partition hoặc chạy model.

## Biên lưu trữ và độ tin cậy

- Repository: `C:\Users\hieu\Documents\ChatGPT\invesment scam intelligence`
- Data root ngoài Git: `D:\nckh 2026-2027\ISI_Data`
- Python: `.venv\Scripts\python.exe`
- Chạy script repository dưới dạng module từ repository root.
- Raw data không được đưa vào Git. Git chỉ chứa protocol, manifest, hash,
  decision, schema và verifier.
- File tồn tại không đồng nghĩa đáng tin; phải lần theo chuỗi SHA-256 từ
  registry đã commit.
- Không mở live candidate domain. Network chỉ chạy qua release đã đóng băng.

## Chuỗi bằng chứng

```text
terms/protocol
  → original bytes + SHA-256
  → offline normalization / exact-text extraction
  → case/entity/domain/clone/near-duplicate grouping
  → primary evidence review
  → blind independent second review
  → reconciliation + owner acceptance
  → group-disjoint development / sealed external holdout
  → predeclared model-development gate
```

Archive availability, registry membership và source identity không tạo label.
Official-reference prose cũng không phải model input cho target task.

## Checkpoint hiện tại

### P2 — Raw QA

`registry/analyses/raw_cross_registry_provenance_audit_v2.json` bao phủ 278/278
file, 1.640.058.635 byte, 278 chuỗi hash rooted từ Git và 0 mismatch. Hai target
lịch sử không tồn tại (`luctra.net`, `finrafx.com`) vẫn bị loại, không tái tạo.

### P3 — External 21

Batch có 10 `CONFIRMED` và 11 `LEGITIMATE`, đủ cho diagnostic/reporting theo
pilot đã đóng băng. Verifier V2 tái kiểm tra raw capture/hash. Provenance vẫn
ghi `independent_human_evidence_rereview=false`; đây không phải double-reviewed
Gold và không record nào đủ điều kiện train.

### P4 — Crimson

AI first pass đã có 40/40, nhưng chỉ 1/40 first human review hoàn tất. Packet V2
giữ 39 first-review task, 1 blind-second task sẵn sàng, 20 blind-second task
đang chờ và 15 official-reference follow-up. Packet không tạo human decision,
label hoặc training eligibility. AI không được tự nhận vai reviewer người thật.

### Target Text Corpus pilot

22 artifact đã qua grouping, primary review, blind second review, reconciliation
và owner acceptance: 4 `CONFIRMED`, 11 `LEGITIMATE`, 7 `UNCERTAIN`. Cả 15 quyết
định dứt khoát vẫn chỉ là diagnostic; development corpus gate chưa đạt.

### P5 — SEC/IAPD timed gate

V4 đã thực thi một lần và dừng đúng hợp đồng trên HTTP 429. Hiện có 115 planned,
92 resolved (45 available, 47 unavailable) và 23 unresolved. V5 chỉ được retry
đúng 23 dòng này, một lần mỗi dòng, với tối thiểu 60 giây/yêu cầu và
`not_before=2026-10-17T01:19:27.607186+07:00`. Capture plan vẫn đóng cho đến khi
independent QA xác nhận không còn unresolved.

Ba V5 entrypoint đã qua preflight import cô lập 3/3, không gọi `main()` và không
network. Tooling hậu-V5 cũng đã được chuẩn bị offline: capture-plan V2 bind đúng
generation V3/V4/V5; capture-release V2 bắt buộc cooldown 24 giờ từ final
availability `created_at`; generic missing-row retry chỉ có thể materialize sau
partial capture QA thật và một cooldown 24 giờ khác. Chưa có plan, capture
release hoặc retry release cụ thể nào được tạo.

### P6 — Manual acquisition

Packet, schema, template và validator đã sẵn sàng. DFPI chỉ nhận lawful
first-party artifact hoặc official export hợp lệ và bắt đầu từ `UNCERTAIN`.
SSC/HNX vẫn bị chặn đến khi có official export/reuse basis hoặc written
permission được kiểm tra độc lập. Intake QA pass không tạo candidate, label,
quota hoặc model permission.

### P7 — Model decision

Source-role audit đã hoàn tất. Mendeley `group_split_v2` là historical
heterogeneous benchmark, không phải verified investment-scam ground truth.
Word unigram+bigram TF-IDF + regularized logistic regression chỉ còn là internal
reference, không deployable. Character sparse, style guard và frozen E5 đều đã
thất bại gate. Không model configuration mới nào được phép trước khi fresh
grouped V1-Core supply và quota ngôn ngữ/channel hoàn tất.

## Lệnh xác minh chuẩn

Chạy từ repository root:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

.venv\Scripts\python.exe -m unittest tests.test_raw_cross_registry_provenance_audit_registry_v2

.venv\Scripts\python.exe -m scripts.verify_external_text_reconciled_pilot_v2 `
  --registry registry\pilots\external_text_reconciled_pilot_v1.json

.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_manual_acquisition_packet_v1 `
  --packet configs\target_text_corpus_v1_manual_acquisition_packet_v1.json

.venv\Scripts\python.exe -m scripts.verify_sec_edgar_iapd_wayback_availability_retry_release_v5 `
  --release configs\sec_edgar_iapd_wayback_availability_retry_release_v5.json

.venv\Scripts\python.exe -m scripts.verify_repository_module_preflight_v2 `
  --config configs\repository_module_preflight_v2.json `
  --report "D:\nckh 2026-2027\ISI_Data\derived\project_module_preflight_v2\module_preflight_report_v2.json"

.venv\Scripts\python.exe -m unittest tests.test_project_state_gap_ledger_v5
.venv\Scripts\python.exe -m unittest tests.test_text_model_choice_dossier_v5
```

Không dùng implementation V1 của external verifier bằng module; file đó được
giữ nguyên vì lý do lịch sử. Dùng verifier V2.

## Việc được phép tiếp theo

1. Heartbeat chạy đúng SEC/IAPD V5 tại hoặc sau `not_before`, dừng ngay trên
   HTTP 429 và xác minh kết quả bằng verifier V5 đã predeclare.
2. Reviewer người thật có thể tiếp tục Crimson theo packet V2 và evidence
   contract; AI không được ghi quyết định thay reviewer.
3. Chủ dự án có thể cung cấp lawful DFPI artifact hoặc bằng chứng export/reuse
   cho SSC/HNX theo packet P6.

Không được tự tạo quota filler, mở live candidate domains, suy nhãn từ
availability/registry/official identity, mở validation/test/holdout, hoặc thử
model/hyperparameter mới.

## Điểm bắt đầu authoritative

1. `registry/analyses/project_state_gap_ledger_v5.json`
2. `registry/analyses/raw_cross_registry_provenance_audit_v2.json`
3. `registry/analyses/external_text_reconciled_pilot_verifier_v2.json`
4. `registry/analyses/crimson_human_review_packets_v2.json`
5. `registry/analyses/target_text_corpus_v1_manual_acquisition_packet_v1.json`
6. `registry/analyses/text_task_source_audit_v1.json`
7. `registry/analyses/text_model_choice_dossier_v5.json`
8. `registry/analyses/sec_edgar_iapd_wayback_availability_retry_release_v5.json`
9. `registry/analyses/sec_edgar_iapd_wayback_availability_result_verifier_v5.json`
10. `registry/analyses/repository_module_preflight_v2.json`
11. `registry/analyses/sec_edgar_iapd_wayback_capture_plan_tooling_v2.json`
12. `registry/analyses/sec_edgar_iapd_wayback_capture_execution_tooling_v2.json`
13. `registry/analyses/sec_edgar_iapd_wayback_capture_retry_tooling_v1.json`

Conversation history chỉ là ngữ cảnh giải thích, không phải artifact có thẩm
quyền.
