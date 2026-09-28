# Crimson human review plan V1

## Mục đích

Kế hoạch này biến 40 AI-assisted first pass thành một hàng đợi mà người review có
thể làm lần lượt. Nó không hoàn tất review, không tạo nhãn và không cho phép dùng
dữ liệu để train.

## Thứ tự ưu tiên

- P0: 2 trường hợp nghi mạo danh, cần kiểm tra đầu tiên và cần hai người review.
- P1: 11 trường hợp cần hai người review và còn URL cơ quan quản lý chưa xác nhận sống.
- P2: 8 trường hợp có URL sống đã xác nhận nhưng vẫn cần hai người review.
- P3: 3 trường hợp chỉ cần một reviewer nhưng còn URL chính thức cần xử lý thủ công.
- P4: 16 trường hợp còn lại, chỉ cần một reviewer kiểm tra official reference.

Tổng cộng có 21 trường hợp cần second review và 16 trường hợp cần xử lý URL chính
thức thủ công. Không mở domain Crimson trên máy chính.

## Cách dùng workbook

1. Mở sheet `Review plan` và làm từ trên xuống.
2. Dùng Pilot ID để xem các dòng tương ứng trong `Evidence`.
3. Chỉ mở URL của cơ quan quản lý trong `Evidence`.
4. Ghi quyết định con người vào các ô vàng của sheet `Review`.
5. Chỉ đặt `COMPLETED` khi đã điền đủ reference check, identity, evidence,
   reviewer, ngày và ghi chú. Nếu cột yêu cầu second review là YES, phải có người
   review thứ hai.

Các cột trạng thái trong `Review plan` lấy công thức trực tiếp từ `Review`, nên
không nhập quyết định ở hai nơi.

## Tiến độ

`PILOT_CRIMSON_REF_018` đã được Hieu xác nhận first human review ngày 2026-09-23.
Trạng thái hiện tại là `COMPLETED` cho review thứ nhất nhưng vẫn
`SECOND_REVIEW_REQUIRED`. Lần kiểm tra lại cũng xác nhận được cả hai nguồn sống,
vì vậy số trường hợp còn cần xử lý URL thủ công trong workbook giảm từ 16 xuống 15.

## Giới hạn

- Gợi ý AI không phải kết luận cuối cùng.
- IOSCO warning không phải bản án hoặc nhãn scam tự động.
- SEC/IAPD registration không phải bằng chứng website an toàn.
- 39 dòng vẫn `IN_PROGRESS`. Một dòng đã hoàn tất first review nhưng chưa đủ điều
  kiện adjudicate. Mọi dòng vẫn `Training eligible = NO`.
