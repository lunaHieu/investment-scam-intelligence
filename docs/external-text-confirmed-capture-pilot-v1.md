# External text confirmed capture pilot V1

## Kết quả

Nhánh `CONFIRMED` đã đạt đủ 10 artefact observed-text dạng website snapshot để
đưa sang human reconciliation. Các artefact được lấy từ raw replay của Internet
Archive; không có truy cập trực tiếp vào live candidate domain.

- 95 ứng viên đã được hỏi availability qua API Internet Archive.
- 25 snapshot gần thời điểm warning được chọn để thử capture.
- 22 raw replay được lưu; 3 replay lỗi hoặc quá ngắn nên không được lưu.
- 10/22 raw capture qua sàng lọc identity, độ dài và tín hiệu
  investment/solicitation; 12 capture còn lại được giữ trong raw và báo cáo
  nhưng không vào intake.
- 10/10 draft qua structural/hash validation; tất cả raw hash khớp manifest.
- First pass đề xuất 10 case để con người xem xét là `CONFIRMED`: 2 `HIGH`, 8
  `MEDIUM_HIGH`.
- Ground truth vẫn là `UNCERTAIN + LOW + IN_REVIEW`; human-reconciled và
  external-evaluation-eligible đều bằng 0.

Review index tổng hợp:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\confirmed_review_index_v1.md`

Raw capture:

`D:\nckh 2026-2027\ISI_Data\raw\external_text_captures\2026-09-24\confirmed_wayback\`

## Phân cách evidence và model input

- Archived candidate page là artefact observed-text có thể trở thành model
  input sau khi human review.
- Official regulator warning chỉ là evidence; warning text không được ghép vào
  trường text của artefact và không được dùng làm model input.
- Warning + archived page không tự tạo label. Reviewer phải xác nhận cùng
  entity/host, thời điểm phù hợp, không có domain repurpose/injected content và
  không có bằng chứng mâu thuẫn chưa giải quyết.

## Phần bị chặn để làm thủ công sau

Bảy case không capture được trang warning chính thức vì HTTP 403 hoặc timeout:

- `CASE_CONF_001`
- `CASE_CONF_005`
- `CASE_RESERVE2_CONF_004`
- `CASE_RESERVE2_CONF_005`
- `CASE_RESERVE2_CONF_008`
- `CASE_RESERVE2_CONF_012`
- `CASE_RESERVE2_CONF_035`

`CASE_RESERVE_CONF_036` có local capture MoneySmart nhưng HTML chỉ chứa app
shell; phần warning riêng của case được nạp động. Các mục này được giữ trong
review index để người nghiên cứu mở URL chính thức và xác nhận sau. Không copy
warning text vào model input.

## Kiểm tra lại

```powershell
.venv\Scripts\python.exe scripts\verify_external_text_confirmed_capture_pilot.py `
  --registry registry\pilots\external_text_confirmed_capture_pilot_v1.json
```

Lệnh chỉ đọc local file, tính lại hash và kiểm tra rằng mọi gate vẫn đóng.
