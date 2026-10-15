# P4P — Crimson human-review packets V2

## Ý nghĩa

P4P biến plan 40 dòng và decision log hiện tại thành các task packet bất biến,
không tự review và không tạo label. Các packet dùng task ID khác nhau; một case
có thể có first-review, second-review và official-reference task riêng vì đó là
ba nghĩa vụ khác nhau, nhưng không task ID nào trùng.

## Kết quả hiện tại

- `first_review_pending_v2.jsonl`: 39 task chưa có first human review.
- `blind_second_review_ready_v2.jsonl`: 1 task đã đủ điều kiện giao reviewer 2.
- `blind_second_review_waiting_v2.jsonl`: 20 task cần second review nhưng đang
  chờ first review hoàn tất.
- `official_reference_followup_v2.jsonl`: 15 task URL official cần kiểm tra thủ
  công. Con số giảm từ 16 trong plan gốc vì decision hiện tại xác nhận mọi URL
  cho `PILOT_CRIMSON_REF_018`.

Blind-second packet không chứa AI identity/evidence suggestion, tên/quyết định
reviewer 1 hoặc ghi chú reviewer 1. Mọi dòng giữ `training_eligible=NO` và
`label_created=false`. Chỉ mở official-reference URL; không mở Crimson host.

## Tạo và xác minh

```powershell
.venv\Scripts\python.exe -m scripts.build_crimson_human_review_packets_v2 `
  --config configs\crimson_human_review_packets_v2.json

.venv\Scripts\python.exe -m scripts.verify_crimson_human_review_packets_v2 `
  --config configs\crimson_human_review_packets_v2.json
```

Output nằm ngoài Git tại
`D:\nckh 2026-2027\ISI_Data\derived\crimson_human_review_packets_v2`.
Builder không overwrite. Packet pass chỉ chuẩn bị công việc cho con người; nó
không được ghi ngược thành decision nếu chưa có xác nhận reviewer rõ ràng.
