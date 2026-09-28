# External text legitimate reserve capture V1

## Kết quả

Mười ứng viên SEC/IAPD đầu tiên trong reserve queue đã được thử. Lần đầu, tầng
HTTP của PowerShell báo lỗi DNS cho cả mười dù `Resolve-DnsName` vẫn trả được IP.
Đây là lỗi resolver của ứng dụng, không phải bằng chứng rằng website ngừng hoạt
động.

Capture V2 dùng A record vừa phân giải cùng `curl --resolve`, nhưng vẫn giữ URL
HTTPS và SNI/certificate theo hostname. Redirect được xử lý từng bước; chỉ host
gốc và biến thể `www` được phép. Kết quả:

- 9 raw HTML capture thành công;
- 1 host (`woodleyfarra.com`) trả HTTP 403 và không bị bypass;
- 9/9 SHA-256 capture hợp lệ, không có structural error;
- tổng số legitimate raw capture của hai pilot hiện là 11.

Raw mới nằm tại:

`D:\nckh 2026-2027\ISI_Data\raw\external_text_captures\2026-09-24\legitimate\`

Derived intake và review brief nằm tại:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\legitimate_reserve_capture_v1\`

## Đối chiếu offline

Cả chín artifact đều thỏa first pass: host xuất hiện chính xác trong SEC filing,
firm là `Registered / APPROVED`, và tên firm xuất hiện trong visible text.
Khuyến nghị cho human review gồm năm `HIGH` và bốn `MEDIUM_HIGH`. Đây chỉ là
khuyến nghị kiểm tra, không phải nhãn.

Tất cả record vẫn giữ `UNCERTAIN + LOW + IN_REVIEW`; human-confirmed bằng 0,
eligible legitimate bằng 0, model scoring và training vẫn đóng. Reviewer cần
kiểm tra raw capture, SEC identity và bằng chứng mâu thuẫn/impersonation trước
khi quyết định bất kỳ record nào là `LEGITIMATE + HIGH + RECONCILED`.

## Kiểm tra lại

```powershell
.venv\Scripts\python.exe scripts\verify_external_text_legitimate_reserve_capture.py `
  --registry registry\pilots\external_text_legitimate_reserve_capture_v1.json
```
