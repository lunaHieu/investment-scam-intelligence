# Reproducibility guide — current project state V2

Snapshot date: 2026-10-15 (Asia/Saigon).

## Tên bước và ý nghĩa

**P8R: cập nhật đường dẫn tái lập sau các nhánh song song.** Guide V2 giữ V1
bất biến nhưng chuyển điểm bắt đầu sang ledger V3, verifier external V2 và
packet thu thập thủ công P6. Đây là bản đồ vận hành; nó không mở gate dữ liệu
hay model.

## Biên lưu trữ và độ tin cậy

- Repository: `C:\Users\hieu\Documents\ChatGPT\invesment scam intelligence`
- Data root ngoài Git: `D:\nckh 2026-2027\ISI_Data`
- Python: `.venv\Scripts\python.exe`
- Raw data không được đưa vào Git. Git chỉ chứa protocol, manifest, hash,
  decision, schema và verifier.
- File tồn tại không đồng nghĩa đáng tin. Raw hiện tại cần chuỗi SHA-256 rooted
  từ artifact đã commit.
- Script repository phải được gọi bằng module từ repository root.
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
pilot đã đóng băng. Verifier V2 chạy được bằng module và tái kiểm tra mọi raw
capture/hash. Provenance vẫn ghi `independent_human_evidence_rereview=false`;
đây không phải double-reviewed Gold và không có record nào đủ điều kiện train.

### P4 — Crimson

AI first pass: 40/40. Human first review: 1/40; còn 39. Có 21 second review và
16 live-source gap. Không record Crimson nào training-eligible.

### Target Text Corpus pilot

22 artifact đã qua grouping, primary review, blind second review, reconciliation
và owner acceptance: 4 `CONFIRMED`, 11 `LEGITIMATE`, 7 `UNCERTAIN`. Cả 15 quyết
định dứt khoát vẫn chỉ là diagnostic; development corpus gate chưa đạt.

### P5 — Capacity và timed gate

SEC/IAPD V4 chỉ được thực thi một lần từ
`2026-10-16T00:48:55.969405+07:00`. Hiện có 115 planned, 84 resolved và 31
unresolved; capture-plan gate vẫn đóng. Vietnamese supply đã kiểm chứng vẫn là
0, trong khi minimum là 8 `CONFIRMED` và 8 `LEGITIMATE` groups.

### P6 — Manual acquisition packet

Packet, schema, template và validator đã sẵn sàng. DFPI chỉ nhận first-party
artifact hoặc official export hợp lệ, tối đa 20 item/submission và bắt đầu từ
`UNCERTAIN`. SSC/HNX vẫn bị chặn đến khi có official export/reuse basis hoặc
written permission được kiểm tra độc lập. Intake QA pass không tạo candidate,
label, quota hay model permission.

### P7 — Model decision

Word unigram+bigram TF-IDF + regularized logistic regression vẫn là internal
reference, không deployable. Character sparse, style guard và frozen E5 đều đã
thất bại gate tương ứng. Không model configuration mới nào được phép trước khi
fresh grouped V1-Core supply và quota ngôn ngữ/channel hoàn tất.

## Lệnh xác minh chuẩn

Chạy từ repository root:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

.venv\Scripts\python.exe -m unittest tests.test_raw_cross_registry_provenance_audit_registry_v2

.venv\Scripts\python.exe -m scripts.verify_external_text_reconciled_pilot_v2 `
  --registry registry\pilots\external_text_reconciled_pilot_v1.json

.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_manual_acquisition_packet_v1 `
  --packet configs\target_text_corpus_v1_manual_acquisition_packet_v1.json

.venv\Scripts\python.exe -m unittest tests.test_project_state_gap_ledger_v3
.venv\Scripts\python.exe -m unittest tests.test_text_model_choice_dossier_v5
```

Không dùng `scripts/verify_external_text_reconciled_pilot.py` bằng module; đó là
implementation V1 đã pin hash và được giữ nguyên vì lý do lịch sử. Dùng V2.

## Việc được phép tiếp theo

1. Heartbeat chạy SEC/IAPD V4 từ `not_before`, dừng ngay trên HTTP 429.
2. Người dùng có thể cung cấp lawful DFPI artifact hoặc bằng chứng export/reuse
   cho SSC/HNX theo packet P6.
3. Reviewer độc lập có thể tiếp tục Crimson.

Không được tự tạo quota filler, mở live candidate domains, đổi review thành
human/Gold, mở validation/test/holdout, hoặc thử model/hyperparameter mới.

## Điểm bắt đầu authoritative

1. `registry/analyses/project_state_gap_ledger_v3.json`
2. `registry/analyses/raw_cross_registry_provenance_audit_v2.json`
3. `registry/analyses/external_text_reconciled_pilot_verifier_v2.json`
4. `registry/analyses/target_text_corpus_v1_manual_acquisition_packet_v1.json`
5. `registry/analyses/text_model_choice_dossier_v5.json`
6. `registry/analyses/sec_edgar_iapd_wayback_availability_retry_release_v4.json`

Conversation history chỉ là ngữ cảnh giải thích, không phải artifact có thẩm
quyền.
