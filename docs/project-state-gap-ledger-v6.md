# Project state ledger V6

## Tên bước và ý nghĩa

**P1R4: hợp nhất trạng thái sau SEC/IAPD V5.** Ledger này thay trạng thái V5 đã tiêu thụ bằng kết quả thực tế 107/115 resolved và release V6 đã được kiểm tra độc lập. Mục đích là ngăn các bước sau sử dụng nhầm con số 92/115 của ledger cũ hoặc mở capture plan khi vẫn còn lỗi.

## Trạng thái hiện tại

- SEC/IAPD đã giải quyết 107/115 candidate: 52 có snapshot, 55 không có snapshot và 8 còn unresolved.
- V5 hoàn tất đúng 23 request, không gặp HTTP 429; independent QA giữ capture plan đóng vì vẫn còn tám lỗi mạng/DNS.
- V6 chỉ được retry đúng tám dòng unresolved, tối đa một lần mỗi dòng, với nhịp tối thiểu 60 giây/request.
- V6 chỉ mở sau `2026-10-18T08:47:59.207293+07:00`; heartbeat dự kiến chạy lúc 08:55 cùng ngày.
- 107 dòng đã resolved phải được giữ nguyên byte-equivalent. Availability không phải captured artifact và không phải label evidence.
- Existing raw integrity vẫn là 278/278 file hiện có, nhưng fresh V1-Core vẫn là 0/300 nhóm phát hành.
- Crimson và manual-source branch vẫn cần human/external input theo ledger V5.
- Capture, labeling, model training/scoring, validation và test vẫn đóng.

## Việc kế tiếp

1. Heartbeat chạy release V6 đúng một lần sau `not_before` và tạo independent QA.
2. Nếu QA đạt `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED`, mới chuẩn bị capture plan riêng biệt bằng tooling V2 đã commit.
3. Nếu vẫn còn unresolved, giữ capture đóng và chỉ chuẩn bị một release mới cho đúng các dòng lỗi sau thêm ít nhất 24 giờ.

Không có acquisition/model step nào khác được ledger này tự động mở.
