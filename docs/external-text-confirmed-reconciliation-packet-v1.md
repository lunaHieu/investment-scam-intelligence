# External text confirmed reconciliation packet V1

## Kết quả

Đã chạy đối soát tự động vòng hai trên 10 draft `CONFIRMED` bằng đúng các
artefact local đã đóng băng. Cả 10/10 raw hash và text hash đều hợp lệ; 10/10
case khớp host, identity, trật tự thời gian, official-warning reference và có
tín hiệu solicitation trong preserved candidate text. Không phát hiện hard
contradiction tự động.

Đây vẫn chỉ là decision aid. Toàn bộ source intake giữ nguyên
`UNCERTAIN + LOW + IN_REVIEW`; human decision bằng 0, eligible bằng 0 và không
có label mới.

Decision packet dễ đọc:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\confirmed_reconciliation_packet_v1\decision_packet_v1.md`

Packet JSON phục vụ kiểm toán:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\confirmed_reconciliation_packet_v1\decision_packet_v1.json`

## Ý nghĩa của các kiểm tra

- `automatic gate`: kiểm tra hash, trạng thái draft, host, identity, thời gian,
  official-warning reference và dấu hiệu solicitation.
- `hard contradiction`: một gate khách quan bị hỏng. Hiện có 0 case.
- `caution`: điểm cần reviewer chú ý nhưng không phải bằng chứng tự động bác bỏ
  case. Ví dụ candidate tự nhận regulated/licensed, không thấy risk disclosure,
  hoặc snapshot cách reference hơn 365 ngày.
- Warning text vẫn chỉ là evidence độc lập, không phải model input.

Phân loại evidence từ metadata đóng băng:

- 5 case `UNREGISTERED_OR_UNLICENSED_WARNING`.
- 3 case `IMPERSONATION_OR_CLONE_WARNING`.
- 2 case `FRAUD_OR_MISCONDUCT_WARNING`.

## Phần còn phải làm thủ công sau

Hai case có local warning capture và identity hiện rõ là `CASE_CONF_008` và
`CASE_RESERVE_CONF_008`.

Tám case còn lại vẫn cần mở trang warning chính thức để xác nhận thủ công:

- Bảy case chưa có local warning capture: `CASE_CONF_001`, `CASE_CONF_005`,
  `CASE_RESERVE2_CONF_004`, `CASE_RESERVE2_CONF_005`,
  `CASE_RESERVE2_CONF_008`, `CASE_RESERVE2_CONF_012`,
  `CASE_RESERVE2_CONF_035`.
- `CASE_RESERVE_CONF_036` có capture MoneySmart nhưng chỉ là app shell, không
  hiện identity của candidate.

Khi review thủ công, không copy warning text vào artefact dùng cho model. Chỉ
ghi quyết định, reviewer, rationale, contradictory-evidence check và confidence
vào bản reconciled mới sau khi đã xác nhận.

## Kiểm tra lại

```powershell
.venv\Scripts\python.exe scripts\verify_external_text_confirmed_reconciliation_packet.py `
  --registry registry\analyses\external_text_confirmed_reconciliation_packet_v1.json
```

Verifier tính lại hash của code, packet, intake và raw capture; đồng thời chứng
minh human decision, external scoring, training và deployment gate vẫn đóng.
