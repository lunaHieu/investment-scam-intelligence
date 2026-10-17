# Data Sufficiency Audit V2

Date: 2026-10-17  
Status: frozen post-V5 amendment

## Tên bước và ý nghĩa

Audit V2 cập nhật riêng tiến độ SEC/IAPD sau V5 và giữ nguyên các mẫu số đã được định nghĩa trong V1. Mục đích là không để 107 kết quả availability bị hiểu nhầm thành 107 raw artifacts hoặc 107 dòng train.

## Trạng thái không thay đổi

- Raw hiện có: 278/278 file được kiểm tra hash, tổng 1.640.058.635 byte. Đây là 100% tính toàn vẹn của raw đang lưu, không phải 100% acquisition plan.
- Historical Mendeley baseline: 3.916 train rows thuộc 3.783 group.
- Fresh V1-Core: 0/300 group được phát hành, tức 0%.
- SEC/IOSCO/IAPD identity and warning indexes vẫn chỉ là reference metadata.
- Validation, test, model promotion và fresh-target training vẫn đóng.

## Thay đổi sau V5

- SEC/IAPD availability resolved tăng từ 92 lên 107 trong tổng 115 candidate.
- 52 candidate có snapshot, 55 không có snapshot và 8 còn lỗi mạng/DNS.
- Availability resolution là 107/115, tương đương 93,04%.
- Raw artifacts được capture từ nhánh này: 0.
- Dòng training-ready được tạo từ nhánh này: 0.
- V6 chỉ retry tám lỗi còn lại sau `2026-10-18T08:47:59.207293+07:00`.

## Kết luận

V5 cải thiện độ hoàn chỉnh của bước discovery/availability, nhưng không thay đổi mức hoàn thành dataset mục tiêu. Dự án vẫn có 3.916 dòng train historical cho baseline nội bộ và 0/300 fresh target groups cho release V1-Core.

Capture plan chỉ có thể được chuẩn bị nếu independent QA của availability cuối cùng xác nhận không còn unresolved row. Ngay cả khi đó, capture, extraction, grouping, hai lượt review và reconciliation vẫn phải hoàn tất trước khi một record có thể được xem xét cho release.
