# Target Text Corpus V1 — A5 language-response preflight V1

## Tên bước và ý nghĩa

Đây là **C3-preflight**: chuẩn bị biểu mẫu và bộ kiểm định cho phản hồi review ngôn ngữ của đúng 42 bản ghi A5 đã được owner chấp nhận. Bước này giúp người duyệt làm việc trên đúng văn bản đã khóa SHA-256, đồng thời ngăn một biểu mẫu còn trống hoặc kết quả do AI tạo bị nhận nhầm là quyết định của con người.

## Kết quả đã khóa

- Template: `D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\owner_accepted_admission_a5_language_response_v1\language_review_response_template_v1.json`
- Số nhiệm vụ: 42, gồm 33 `DEVELOPMENT` và 9 `EXTERNAL_HOLDOUT`.
- SHA-256 template: `f2e26774053d526e3355d2b8fe75713216782de8ba1bc5271e63eda2d36ed31c`.
- QA độc lập: `PASS_C3_PREFLIGHT_EXACT_42_TEMPLATE_AND_VERIFIER_READY_HUMAN_RESPONSE_ABSENT`.
- SHA-256 QA: `04ccde6868cfe319aa3e1295ff389cc9372a4509b97b48384b1f52e4a3c50f07`.

Mỗi dòng template giữ nguyên `review_item_id`, `record_id`, cohort, đường dẫn văn bản, SHA-256 và số ký tự khác khoảng trắng. Các trường quyết định vẫn để trống và trạng thái template là `TEMPLATE_NOT_A_COMPLETED_RESPONSE`.

## Điều kiện để C3 thực sự hoàn tất

Một người duyệt phải trực tiếp đọc từng file văn bản đã kiểm tra hash, điền mã ngôn ngữ chữ thường theo mẫu BCP-47 giới hạn, thời điểm và lý do, rồi xác nhận rõ rằng gợi ý tự động/AI không được dùng làm bằng chứng cuối cùng. Verifier sẽ từ chối thiếu dòng, thừa dòng, đổi thứ tự, đổi hash, sửa cohort, thiếu xác nhận con người, mã ngôn ngữ sai hoặc phản hồi một phần.

## Những gì bước này không làm

- Không tạo hay giả mạo quyết định của con người.
- Không đổi nhãn `LEGITIMATE`, cohort hay quyết định owner acceptance.
- Không cấp credit vào V1-Core; hiện vẫn là 0/300.
- Không mở validation/test, không score hoặc train model.
- Không thực hiện thao tác mạng hoặc truy cập domain ứng viên.

## Lệnh tái kiểm tra sau khi có phản hồi thật

Chạy từ gốc repository bằng môi trường dự án:

```powershell
.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_a5_language_review_response_v1 --config configs/target_text_corpus_v1_a5_language_review_response_protocol_v1.json --response "D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\owner_accepted_admission_a5_language_response_v1\completed_language_review_response_v1.json" --output "D:\nckh 2026-2027\ISI_Data\derived\target_text_corpus_v1_reference_inputs\owner_accepted_admission_a5_language_response_v1\independent_response_qa_v1.json"
```

Chỉ QA `PASS_EXACT_42_HUMAN_LANGUAGE_RESPONSE_HASH_RECOMPUTED` mới cho phép tính lại nguồn cung ngôn ngữ. Việc đó vẫn không tự động tạo bản ghi train.
