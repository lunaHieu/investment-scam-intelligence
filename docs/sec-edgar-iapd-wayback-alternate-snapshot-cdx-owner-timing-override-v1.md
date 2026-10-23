# SEC EDGAR/IAPD A1 CDX owner timing override V1

## Tên bước và ý nghĩa

Đây là **A1 timing override**: chủ dự án cho phép bỏ phần thời gian còn lại trước `not_before` của release V1 để chạy ngay một truy vấn metadata CDX. Release V1 không bị sửa; ngoại lệ được lưu thành artifact mới có hash và QA độc lập.

## Phạm vi ngoại lệ

- Chỉ đổi thời điểm được bắt đầu từ `2026-10-23T23:35:43.595958+07:00` thành `2026-10-23T21:30:50.846253+07:00`.
- Chỉ một execution và tối đa một logical request.
- Vẫn chờ tối thiểu 60 giây trước request và dừng ngay nếu HTTP 429.
- Chỉ gọi endpoint metadata `web.archive.org/cdx/search/cdx`.
- Không tải archived page, không gọi live candidate domain, không capture, không tạo nhãn và không mở model gate.
- Output/partial journal vẫn no-overwrite và không auto-resume.

## QA trước execution

QA độc lập có trạng thái `PASS_EXPLICIT_OWNER_TIMING_ONLY_OVERRIDE_ONE_REQUEST_SAFETY_UNCHANGED`. Việc execution chỉ được phép dùng executor override đã khóa hash; V1 executor và V1 release vẫn giữ nguyên để bảo toàn lịch sử.

Nếu có alternate metadata candidate, kết quả chỉ cho phép chuẩn bị một capture release riêng. Nó không tự cấp quyền capture hoặc thay đổi population 56 dòng đã review.
