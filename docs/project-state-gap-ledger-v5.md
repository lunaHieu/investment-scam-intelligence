# Project state ledger V5

## Tên bước và ý nghĩa

**P1R3: hợp nhất trạng thái sau lần chạy SEC/IAPD V4.** Ledger này giữ nguyên
các nhánh đã hoàn tất trong V4, ghi nhận kết quả availability thực tế và thay
gate V4 đã tiêu thụ bằng release V5 đã đóng băng.

## Trạng thái hiện tại

- SEC/IAPD đã giải quyết 92/115 ứng viên: 45 có snapshot, 47 không có snapshot
  và 23 còn unresolved. V4 dừng đúng hợp đồng khi gặp HTTP 429.
- V5 chỉ được retry đúng 23 dòng unresolved, tối đa một lần mỗi dòng, với nhịp
  tối thiểu 60 giây/yêu cầu và `not_before` là
  `2026-10-17T01:19:27.607186+07:00`.
- Capture plan vẫn đóng cho đến khi independent QA xác nhận không còn dòng
  unresolved.
- Crimson còn 39 first-review task, 1 blind-second task sẵn sàng và 15
  official-reference follow-up.
- DFPI chỉ có thể intake khi chủ dự án cung cấp lawful first-party artifact;
  SSC/HNX vẫn cần export/reuse basis.
- Model, validation/test, capture và live candidate-domain gates vẫn đóng.

## Việc kế tiếp

1. Heartbeat chạy release V5 sau thời điểm `not_before` và xác minh kết quả độc
   lập.
2. Reviewer/evidence bên ngoài có thể mở lại Crimson hoặc manual-source branch.
3. Chỉ khi V5 đạt `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` mới được chuẩn bị
   capture plan riêng biệt.

Không có nhánh chuẩn bị offline độc lập còn lại có thể tạo thêm dữ liệu đủ điều
kiện mà không lặp việc đã làm hoặc vượt gate hiện hành.
