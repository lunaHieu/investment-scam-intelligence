# Crimson external-reference review pilot V1

## Mục đích

Pilot này biến hàng đợi đối chiếu Crimson–IOSCO/SEC thành một quy trình review
thủ công có kiểm soát. Nó chưa tạo nhãn cho model và không yêu cầu mở trực tiếp
domain Crimson.

## Cách chọn 40 host

Protocol được khóa trước khi review:

- Toàn bộ 8 SEC/IAPD match.
- 12 IOSCO exact-host có reference host xuất hiện trong nhiều record nguồn.
- 10 IOSCO host-hierarchy candidate.
- 10 IOSCO exact-host còn lại được chọn bằng SHA-256 với seed `20260923`.

Kết quả gồm 40 pilot record và 61 evidence record. Cách chọn không phụ thuộc vào
kết luận của reviewer và có thể tái lập từ hai artifact match V1.

## Workbook

Workbook có bốn sheet:

- `Review`: một dòng cho mỗi canonical host, với các ô màu vàng là phần người
  review cần điền. Các công thức xác định khi nào hồ sơ đủ thông tin để adjudicate.
- `Review plan`: xếp 40 host theo P0–P4, ghi hành động con người cần làm và liên
  kết trực tiếp trạng thái từ `Review`. Hai ca nghi mạo danh đứng đầu hàng đợi.
- `Evidence`: từng record IOSCO hoặc SEC/IAPD liên quan, gồm source record ID,
  quan hệ hostname và official reference locator.
- `Guide`: trình tự review và định nghĩa các giá trị được phép.

Một record chỉ trở thành `READY_FOR_ADJUDICATION` sau khi có trạng thái hoàn tất,
xác nhận đã kiểm tra official reference, đánh giá quan hệ danh tính, đánh giá bằng
chứng, reviewer, ngày và ghi chú. Trường hợp nghi mạo danh, chưa rõ danh tính hoặc
host tham chiếu dùng chung bắt buộc review lần hai.

## Giới hạn

- `Training eligible` luôn là `NO` trong pilot này.
- `SAME_ENTITY` không có nghĩa là hợp pháp hoặc an toàn.
- `IMPERSONATION_SUSPECTED` vẫn cần adjudication; không phải nhãn scam tự động.
- IOSCO warning không phải bản án và SEC registration không loại trừ mạo danh.
- Không tìm thấy reference không có nghĩa là domain an toàn.

## Tiến độ human review

`PILOT_CRIMSON_REF_018` đã hoàn tất first human review ngày 2026-09-23 với
`IMPERSONATION_SUSPECTED` và `WARNING_RELEVANT`. Vì đây là ca nghi mạo danh,
workbook giữ `SECOND_REVIEW_REQUIRED`; chưa có dòng nào sẵn sàng để adjudicate
hoặc dùng cho training.

## Kiểm định

- Toàn bộ artifact được khóa SHA-256 trong pilot registry.
- Workbook có đúng bốn sheet, không chứa VBA, có dropdown cho trường review và
  công thức trạng thái cho 40 dòng.
- Đã thử luồng hoàn tất thông thường và luồng bắt buộc review lần hai; sau thử
  nghiệm mọi ô được trả về trạng thái chưa review.
- Workbook đã được export, mở lại bằng spreadsheet engine, quét lỗi công thức và
  kiểm tra trực quan từng sheet.
