# Target Text Corpus V1 — C2 external artifact intake preflight V1

## Tên bước và ý nghĩa

Đây là **C2-preflight**: chuẩn bị một cổng tiếp nhận offline thống nhất cho artifact hoặc hồ sơ quyền từ CFTC, DFPI, SSC và HNX. Mục tiêu là mọi file ngoài dự án đều phải qua cùng một chuỗi kiểm tra nguồn chính thức, vị trí lưu, byte-size, SHA-256, căn cứ sử dụng và dữ liệu cá nhân trước khi có bất kỳ bước enumeration nào.

## Trạng thái từng nguồn

- `cftc_red_list`: artifact nguyên gốc do người dùng cung cấp hoặc official export có thể vào QA; mục tiêu tham chiếu 75 group nhưng membership không tạo nhãn.
- `dfpi_crypto_scam_tracker`: artifact first-party/official export có thể vào QA; complaint chỉ là case seed `UNCERTAIN`.
- `ssc_vietnam_investor_warnings`: hiện chỉ nhận hồ sơ quyền. Source artifact bị chặn cho đến khi có readiness ledger riêng xác nhận export/reuse basis.
- `hnx_vietnam_issuer_profiles`: hiện chỉ nhận hồ sơ quyền. Hồ sơ danh tính không tự tạo nhãn `LEGITIMATE`.

## Kết quả đã khóa

- Template ngoài Git: `D:\nckh 2026-2027\ISI_Data\governance\target_text_corpus_v1\external_artifact_intake_v1\submission_template_v1.json`.
- Template SHA-256: `8a5dca17fe372ec260f82eb1af633864339b240ed1d3a96bc29722a5a0bcb6fc`.
- Tooling QA: `PASS_C2_PREFLIGHT_FOUR_SOURCE_INTAKE_READY_EXTERNAL_INPUTS_ABSENT`.
- QA SHA-256: `53001f7899a2bdfb18f18a5900cbd11b63d2b8e070c17e60420387c2e3c4fa2f`.

Verifier từ chối host ngoài allowlist, HTTP không mã hóa, mode sai, căn cứ quyền không phù hợp, traversal khỏi data root, trùng đường dẫn, thiếu file, sai số byte, sai SHA-256, cho phép redistribution, hoặc cố nộp source artifact SSC/HNX trước readiness ledger.

## Khi có artifact thật

Sao chép template, bỏ `template_id` và `instructions`, thay toàn bộ giá trị mẫu và đặt status `PENDING_INDEPENDENT_C2_INTAKE_QA`. File submission và hồ sơ quyền có danh tính vẫn ở ổ D, không commit vào Git công khai.

```powershell
.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_c2_external_artifact_intake_v1 --config configs/target_text_corpus_v1_c2_external_artifact_intake_protocol_v1.json --submission "D:\nckh 2026-2027\ISI_Data\governance\target_text_corpus_v1\external_artifact_intake_v1\completed_submission_v1.json" --data-root "D:\nckh 2026-2027\ISI_Data" --output "D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\external_artifact_intake_preflight_v1\independent_submission_qa_v1.json"
```

Một submission PASS chỉ mở bước tạo readiness ledger mới; nó không tạo candidate, nhãn, quota, model input hoặc quyền truy cập domain ứng viên.
