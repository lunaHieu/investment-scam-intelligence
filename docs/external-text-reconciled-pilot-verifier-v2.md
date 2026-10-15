# External-text reconciled pilot verifier V2

## Tên bước và ý nghĩa

**P3T: sửa khả năng tái kiểm tra, không sửa dữ liệu.** Verifier V1 đã được pin
trong registry lịch sử nhưng dùng import theo script path, nên thất bại khi gọi
theo chuẩn module của dự án. V2 được tạo thành file mới; V1, raw capture, intake,
21 quyết định và validation report không bị sửa.

Chạy từ repository root:

```powershell
.venv\Scripts\python.exe -m scripts.verify_external_text_reconciled_pilot_v2 `
  --registry registry\pilots\external_text_reconciled_pilot_v1.json
```

Verifier V2:

- kiểm tra lại mọi SHA-256 được pilot registry pin;
- chạy lại validator offline trên 21 capture gốc;
- yêu cầu đúng 10 `CONFIRMED`, 11 `LEGITIMATE`, 21 record reporting-eligible;
- yêu cầu mọi record vẫn ghi `independent_human_evidence_rereview = false`;
- từ chối nếu pilot bị mô tả thành double-reviewed Gold benchmark;
- yêu cầu model fit/scoring bằng 0 và training/deployment vẫn đóng.

Kết quả pass chỉ khôi phục khả năng tái kiểm tra bằng module. Nó không nâng chất
lượng review, không tạo nhãn mới và không làm 21 record đủ điều kiện training.
