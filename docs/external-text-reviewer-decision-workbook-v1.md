# External-text reviewer decision workbook V1

## Mục đích

Workbook gom 10 case `CONFIRMED` và 11 case `LEGITIMATE` thành 21 form review
có cùng một contract. Tất cả form ban đầu đều `PENDING`; quyết định, reviewer,
confidence, rationale và confirmation source đều để trống.

Workbook dễ đọc:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\reviewer_decision_workbook_v1\reviewer_decision_workbook_v1.md`

Workbook JSON phục vụ ghi nhận có validation:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\reviewer_decision_workbook_v1\reviewer_decision_workbook_v1.json`

## Thứ tự review

- `P1`: 2 case CONFIRMED đã có local warning hiện identity.
- `P2`: 8 case CONFIRMED cần kiểm tra warning thủ công.
- `P3`: 6 case LEGITIMATE có identity/contact alignment mạnh.
- `P4`: 5 case LEGITIMATE cần kiểm tra kỹ hơn về contact, text ngắn hoặc site
  control.

## Guardrails

- CONFIRMED chỉ chấp nhận final decision `CONFIRMED` hoặc `UNCERTAIN`.
- LEGITIMATE chỉ chấp nhận final decision `LEGITIMATE` hoặc `UNCERTAIN`.
- Cần explicit human confirmation và hoàn tất checklist của đúng nhánh.
- Không cho kết luận mục tiêu nếu còn unresolved contradiction.
- Chỉ decision mục tiêu với confidence `HIGH` mới có thể được đánh dấu
  `ready_for_reconciled_intake`.
- Ghi quyết định không trực tiếp sửa source intake, không tạo label và không mở
  external scoring. Materialization là một bước riêng phải validate lại.

## Công cụ ghi quyết định sau này

`scripts/record_external_text_reviewer_decision.py` đọc một workbook, ghi đúng
một quyết định vào file phiên bản mới và từ chối overwrite. Công cụ yêu cầu đầy
đủ reviewer, thời điểm, rationale, confirmation source và hai cờ xác nhận rõ
ràng. Hiện chưa chạy công cụ này vì các bước review thủ công được hoãn lại.

## Kiểm tra workbook hiện tại

```powershell
.venv\Scripts\python.exe scripts\verify_external_text_reviewer_decision_workbook.py `
  --registry registry\analyses\external_text_reviewer_decision_workbook_v1.json
```

Verifier phải trả về 21 pending, 0 completed, 0 labels và 0 external-eligible.
