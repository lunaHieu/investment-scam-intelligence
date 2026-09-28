# External text legitimate reconciliation packet V1

## Kết quả

Đã chạy đối soát tự động vòng hai trên 11 draft `LEGITIMATE` bằng raw capture,
normalized text, SEC/IAPD profile và first-pass metadata đã đóng băng.

- 11/11 raw hash và text hash hợp lệ.
- 11/11 case khớp CRD, SEC-filed host, firm identity, trạng thái
  `Registered/APPROVED` và trật tự filing/capture.
- 0 hard contradiction tự động.
- 6 đề xuất `HIGH_FOR_HUMAN_REVIEW`, 5 đề xuất
  `MEDIUM_HIGH_FOR_HUMAN_REVIEW`.
- Source intake vẫn `UNCERTAIN + LOW + IN_REVIEW`; human decision, label và
  eligible đều bằng 0.

Decision packet dễ đọc:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\legitimate_reconciliation_packet_v1\decision_packet_v1.md`

Packet JSON phục vụ kiểm toán:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\legitimate_reconciliation_packet_v1\decision_packet_v1.json`

## Cách diễn giải

SEC/IAPD `Registered/APPROVED` và exact filed host là identity evidence. Chúng
không phải chứng nhận rằng mọi claim trên website đều an toàn, không phải bằng
chứng không có compromise, và không tự sinh nhãn `LEGITIMATE`.

Các caution đáng chú ý:

- `CASE_LEGIT_004` và `CASE_RESERVE_LEGIT_005`: visible text ngắn dưới 500 ký
  tự và không khớp contact field từ SEC capture.
- `CASE_RESERVE_LEGIT_001`: 0/5 contact fields hiện trong landing-page text.
- `CASE_RESERVE_LEGIT_007` và `CASE_RESERVE_LEGIT_010`: chỉ khớp 1 contact
  field.
- Return/performance hoặc regulatory/safety wording chỉ được trích thành bounded
  contexts để reviewer đọc; chúng không bị tự động coi là scam hay legitimate.

## Phần còn phải làm thủ công

Cả 11 case vẫn cần reviewer xác nhận site control ở thời điểm capture, kiểm tra
impersonation/compromise, nội dung gây hiểu nhầm và adverse regulator evidence.
Chỉ sau đó mới được tạo một intake reconciled mới với quyết định, reviewer,
rationale và confidence cụ thể.

## Kiểm tra lại

```powershell
.venv\Scripts\python.exe scripts\verify_external_text_legitimate_reconciliation_packet.py `
  --registry registry\analyses\external_text_legitimate_reconciliation_packet_v1.json
```

Verifier tính lại hash code, packet, intake và raw capture, đồng thời kiểm tra
human decision, external scoring, training và deployment gate vẫn đóng.
