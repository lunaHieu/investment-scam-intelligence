# Phiếu đánh giá bằng chứng — PILOT_CRIMSON_REF_016

## Đối tượng và phạm vi

- Host ứng viên: `magnomicyieldltd.com`.
- Chỉ dùng nguồn quản lý chính thức đã ghim trong V3; không mở host ứng viên.
- Đây là đề xuất AI hỗ trợ reviewer, chưa phải quyết định human review.

## Bằng chứng

Thông cáo CONSOB tiếng Anh ngày 20/06/2025 nói cơ quan này ra lệnh chặn bảy
website cung cấp trái phép dịch vụ/sản phẩm tài chính. Danh sách nêu
“Magnomic Yield Ltd” cùng đúng website `magnomicyieldltd.com`.

Nguồn: [CONSOB — Abusive financial services: Consob blacks out 7 abusive websites](https://www.consob.it/documents/d/asset-library-1912910/press_20250620).

Trang “warnings/latests” từng bị thử thách bot không được mở lại hoặc vượt qua;
PDF trên là nguồn CONSOB thay thế và độc lập theo URL. Không có website ứng viên
nào được truy cập. Không có bản PDF thô được tải/lưu vào dự án.

## Đề xuất AI để reviewer kiểm tra

- `Official reference checked`: `YES` — nguồn CONSOB nêu trên đã được đọc trực tiếp.
- `Identity relationship`: `SAME_ENTITY` — thông cáo ghép tên Magnomic Yield Ltd
  với đúng host ứng viên.
- `Evidence assessment`: `WARNING_RELEVANT` — thông cáo mô tả lệnh chặn các
  website bị xem là cung cấp dịch vụ/sản phẩm tài chính trái phép.
- `Second review required`: `YES` — theo kế hoạch review hiện hành.

Giới hạn: một thông cáo quản lý không chứng minh nội dung của bất kỳ email/tin
nhắn cụ thể nào, không phải phán quyết hình sự, và không tự tạo nhãn
`SCAM`. Nếu reviewer thấy chưa đủ để gắn quan hệ, đề xuất phải được hạ xuống
`UNCLEAR`/`INSUFFICIENT_EVIDENCE`; model disposition vẫn là `UNCERTAIN`.

## Trạng thái

Chưa ghi human decision, chưa hoàn thành primary review, chưa chạy blind second
review, chưa reconciliation, chưa admission/label. Reviewer cần xác nhận hoặc
bác đề xuất này qua workflow human-review hiện hành; second review phải do một
người khác thực hiện và không được thấy primary decision hay gợi ý AI.
