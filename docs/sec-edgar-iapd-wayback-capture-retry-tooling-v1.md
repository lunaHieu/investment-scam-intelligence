# SEC EDGAR/IAPD missing-row capture retry tooling V1

## Tên bước và ý nghĩa

Công cụ này chuẩn bị một release retry bất biến chỉ khi capture QA độc lập V1 đã
xác nhận kết quả partial. QA thật chỉ chứa bốn hash trong `inputs`, không chứa
artifact path. Vì vậy builder nhận tường minh `--partial-qa`,
`--source-release`, `--source-release-qa` và `--capture-report`; capture plan
được lấy duy nhất từ `source-release.inputs.capture_plan`.

Builder bắt buộc `verification_id`, status, `errors=[]` và decisions đúng schema
của `scripts.verify_sec_edgar_iapd_wayback_capture_result_v1`. Bốn hash QA
`release_sha256`, `release_qa_sha256`, `report_sha256`, `plan_sha256` phải khớp
chính xác với các artifact tường minh và plan được source release ghim.
Ngoài đối chiếu từng trường, cả builder và verifier retry đều gọi lại verifier
capture-result V1 và yêu cầu object recompute phải bằng đúng QA được cung cấp.

Builder đối chiếu lại plan với report theo nguyên thứ tự. Dòng `CAPTURED` được
giữ trong `completed_capture_ledger` cùng byte count và SHA-256 đã recompute từ
raw file. Chỉ dòng `FAILED` hoặc `NOT_ATTEMPTED_AFTER_HTTP_429_STOP` được đưa vào
`retry_rows`; raw target của các dòng này phải chưa tồn tại. Vì vậy retry không
tải lại hoặc ghi đè một capture đã hoàn tất.

Release bắt buộc:

- `not_before` ít nhất 24 giờ sau `created_at` của partial capture report;
- chỉ dùng `https://web.archive.org` raw replay URL;
- tối đa một attempt cho mỗi snapshot, tối thiểu 30 giây giữa request;
- dừng ngay khi gặp HTTP 429;
- không overwrite report, partial report hoặc raw capture;
- giữ text extraction, label, validation/test, training và scoring đóng.

Verifier độc lập đọc lại QA và toàn bộ artifact đã ghim, chạy lại full capture
result QA, recompute byte/hash của các dòng hoàn tất, tái tạo chính xác
population retry và kiểm tra toàn bộ contract.

Giao diện builder dự kiến khi có partial QA thật:

```powershell
.venv\Scripts\python.exe -m scripts.build_sec_edgar_iapd_wayback_capture_retry_release_v1 `
  --partial-qa <independent-partial-qa.json> `
  --source-release <source-capture-release.json> `
  --source-release-qa <source-capture-release-qa.json> `
  --capture-report <partial-capture-report.json> `
  --created-at <timezone-aware-timestamp> `
  --not-before <at-least-24h-after-report-created-at> `
  --report <new-retry-report.json> `
  --output <new-retry-release.json>
```

Đây chỉ là tooling offline. Chưa có concrete retry release hoặc network request
nào được tạo bởi bước này. Khi một partial capture thực sự xuất hiện, các path
tường minh phải được cung cấp cùng QA hash-only nguyên bản; không sửa hoặc mở
rộng QA lịch sử. Sau đó mới được materialize và đăng ký một release riêng biệt.
