# External text capture candidate queue V1

## Quyết định

Không tải hàng loạt thêm registry trước khi có external text. V1 chọn một hàng
đợi dự phòng gồm 15 ứng viên từ IOSCO và 15 ứng viên từ SEC/IAPD. Mục tiêu là
thu được ít nhất 10 artifact `CONFIRMED` và 10 artifact `LEGITIMATE` sau capture,
đối chiếu danh tính và reconciliation. Ba mươi ứng viên không phải ba mươi nhãn.

## Bộ lọc trước khi chọn

- Chỉ dùng reference index có SHA-256 đã khóa.
- Mỗi ứng viên phải có đúng một host sạch và entity key không rỗng.
- Loại mạng xã hội/nền tảng dùng chung, host SEC xuất hiện ở nhiều firm và host
  đồng thời xuất hiện trong IOSCO.
- Nhánh SEC chỉ nhận firm `Registered` có trạng thái `APPROVED`.
- Nhánh IOSCO cần HTTPS regulator notice, regulator/jurisdiction đầy đủ và không
  nhận notice đặt ngay trên candidate host.
- Chọn tái lập bằng seed; nhánh IOSCO giới hạn sơ bộ theo jurisdiction để tránh
  pilot bị chi phối bởi một cơ quan.

## Ý nghĩa của hai nhánh

`CONFIRMED_CANDIDATE` chỉ có nghĩa là có regulator-warning evidence đáng xem
tiếp. Không mở live suspicious domain theo mặc định. Artifact nên đến từ bản lưu
lịch sử, exhibit, screenshot hoặc nội dung solicitation được regulator bảo tồn.
Warning text không được dùng thay cho nội dung mà model phải phân loại.

`LEGITIMATE_CANDIDATE` chỉ có nghĩa là SEC/IAPD cung cấp registration reference
và host ứng viên đủ sạch để xác minh tiếp. Reviewer phải khớp đúng firm, host và
nội dung capture; registration không chứng minh mọi offer hoặc người tự nhận đại
diện firm đều hợp pháp.

## Trạng thái ban đầu bắt buộc

Mọi record đều bắt đầu với:

- `artifact_capture: MISSING`
- `identity_resolution: UNRESOLVED`
- `ground_truth_status: UNCERTAIN`
- `label_confidence: LOW`
- `review_status: UNREVIEWED`
- `training_eligible: NO`

Hàng đợi không mở test, không chạy model, không tạo label và không cho phép
training. Sau khi có capture, record phải đi qua
`scripts/validate_external_text_intake.py`; chỉ record `HIGH + RECONCILED` có
evidence phù hợp mới có thể đóng góp vào gate `10 + 10`.

## Tái tạo

```powershell
.venv\Scripts\python.exe scripts\select_external_text_capture_candidates.py `
  --queue-output "D:\nckh 2026-2027\ISI_Data\curated\external_text_capture_queue_v1\capture_candidates_v1.jsonl" `
  --report "D:\nckh 2026-2027\ISI_Data\curated\external_text_capture_queue_v1\selection_report_v1.json"
```

## Hàng đợi dự phòng SEC ngày 2026-09-24

Đợt capture chính chỉ lấy được hai artifact SEC; 13 ứng viên còn lại không tạo
đủ dữ liệu, trong đó mười trường hợp gặp lỗi DNS của môi trường. Vì vậy dự án đã
tạo thêm 30 ứng viên dự phòng hoàn toàn offline, không thay đổi 30 ứng viên gốc.

Reserve V1 bổ sung các điều kiện: host chưa xuất hiện trong queue chính, host
không va chạm IOSCO, host duy nhất trong SEC, firm đã đăng ký trước năm 2024,
filing từ năm 2025 trở đi và độ khớp tên firm–domain tối thiểu `0.45`. Trong
2.222 record đạt điều kiện, 30 record đứng đầu đều có affinity `1.0`.

Kết quả được khóa tại
`D:\nckh 2026-2027\ISI_Data\curated\external_text_capture_queue_v1\sec_legitimate_reserve_v1.jsonl`.
Đây vẫn là queue thu thập: 30 record đều `UNCERTAIN`, `LOW`, `UNREVIEWED`,
`training_eligible: NO`; hiện chưa record nào được capture, reconcile hoặc đưa
vào external evaluation.

```powershell
.venv\Scripts\python.exe scripts\select_sec_legitimate_capture_reserve.py `
  --queue-output "D:\nckh 2026-2027\ISI_Data\curated\external_text_capture_queue_v1\sec_legitimate_reserve_v1.jsonl" `
  --report "D:\nckh 2026-2027\ISI_Data\curated\external_text_capture_queue_v1\sec_legitimate_reserve_selection_report_v1.json"
```
