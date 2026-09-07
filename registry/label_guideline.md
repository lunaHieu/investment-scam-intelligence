# ISI V1 Label Guideline

## Gán nhãn ở cấp case

Một `CASE` biểu diễn campaign, entity hoặc sự kiện lừa đảo có các artifact liên quan. Không tạo case mới chỉ vì xuất hiện thêm screenshot, bài đăng hoặc URL của cùng campaign.

`ARTIFACT` có thể là post, message, image, URL, website snapshot, account snapshot, complaint hay warning document. Warning document là evidence; không được mặc định đưa văn bản cảnh báo đó vào lớp positive content.

## Trạng thái ground truth

| Status | Khi dùng |
| --- | --- |
| `CONFIRMED` | Có enforcement/court finding, hoặc nhiều evidence mạnh liên kết trực tiếp tới target artifact/case. |
| `LEGITIMATE` | Có evidence đáng tin về entity/content hợp pháp; vẫn cần tách entity legitimacy và content legitimacy. |
| `UNCERTAIN` | Candidate chưa đủ chứng cứ, evidence mâu thuẫn hoặc không thể liên kết case. Không ép thành binary. |

Gắn `label_confidence` là `HIGH`, `MEDIUM` hoặc `LOW`, kèm rationale và evidence IDs. `CONFIRMED` không đồng nghĩa “legal conviction” nếu evidence chỉ là regulatory warning; hãy ghi chính xác semantics trong rationale.

## Quy trình review

1. Lưu raw record, source label và provenance nguyên vẹn.
2. Chuẩn hóa artifact; tạo candidate link dựa trên domain, entity, payment channel, text/ảnh gần trùng hoặc campaign cue.
3. Reviewer xem evidence trực tiếp, gán/điều chỉnh case label, subtype chính và tactics phụ.
4. Reviewer thứ hai xem subset curated sau khi guideline ổn định; reconcile disagreement và ghi decision log.
5. Chỉ export sample ML từ case đã qua quy tắc split và leakage audit.

## Quy tắc chống shortcut và leakage

- Không lấy `source_id`, `ground_truth_status`, `label_confidence`, `evidence_type`, `review_notes`, `verification_status` hay loại `warning document` làm feature.
- Không để cùng case/campaign, domain family hoặc near-duplicate group xuất hiện ở cả train và evaluation.
- Không sử dụng Gold set để chọn model, threshold hay feature.
- External lookup chỉ được dùng tại inference nếu runtime-observable, có timestamp hợp lệ và được đánh giá riêng.
