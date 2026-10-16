# Repository module preflight V2

## Ý nghĩa

V2 thay phạm vi V4 lịch sử của preflight V1 bằng đúng ba entrypoint SEC/IAPD V5
đang cần cho timed gate hiện hành: retry executor, release verifier và result
verifier. Mỗi module được import trong một subprocess riêng bằng Python của project
venv, có timeout, không gọi `main()`, không ghi bytecode và không overwrite report.

Chạy report bất biến một lần:

```powershell
.venv\Scripts\python.exe -m scripts.run_repository_module_preflight_v2 `
  --config configs\repository_module_preflight_v2.json
```

Xác minh độc lập:

```powershell
.venv\Scripts\python.exe -m scripts.verify_repository_module_preflight_v2 `
  --config configs\repository_module_preflight_v2.json `
  --report "D:\nckh 2026-2027\ISI_Data\derived\project_module_preflight_v2\module_preflight_report_v2.json"
```

PASS chỉ chứng minh đúng ba source đã pin hash import được trong subprocess. Nó
không gọi executor, không gửi network request, không cho chạy V5 trước
`not_before`, và không mở capture, label, validation/test, training hay scoring.

Preflight V1 được giữ nguyên như snapshot lịch sử của V4. V2 không thay đổi bất
kỳ report, raw artifact hoặc quyết định cũ nào.
