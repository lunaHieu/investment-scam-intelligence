# P9 — Active module preflight V1

## Ý nghĩa

P9 kiểm tra năm entrypoint còn hoạt động bằng đúng cách gọi module của dự án.
Mỗi module được import trong subprocess riêng bằng Python hiện tại, có timeout,
không gọi `main()`, không ghi bytecode và không cho phép overwrite report.

Phạm vi gồm ba module SEC/IAPD V4, verifier external 21 V2 và verifier packet
P6. Audit không cố sửa mọi script lịch sử vì nhiều implementation đã được pin
hash; một lỗi lịch sử chỉ được thay bằng version mới khi entrypoint đó còn cần.

Chạy một lần:

```powershell
.venv\Scripts\python.exe -m scripts.run_repository_module_preflight_v1 `
  --config configs\repository_module_preflight_v1.json
```

Xác minh report:

```powershell
.venv\Scripts\python.exe -m scripts.verify_repository_module_preflight_v1 `
  --config configs\repository_module_preflight_v1.json `
  --report "D:\nckh 2026-2027\ISI_Data\derived\project_module_preflight_v1\module_preflight_report_v1_release.json"
```

Pass chỉ chứng minh module import được và source hash không đổi. Nó không chứng
minh network endpoint sẵn sàng, không thực thi V4 sớm và không mở capture,
label, validation/test hoặc model gate.

Một dry-run trước thời điểm freeze được giữ ngoài registry và không có thẩm
quyền. Verifier yêu cầu report chính thức không được có thời gian sớm hơn
`frozen_at` và report chính thức dùng tên file riêng, không overwrite dry-run.
