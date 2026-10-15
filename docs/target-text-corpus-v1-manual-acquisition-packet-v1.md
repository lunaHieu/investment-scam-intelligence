# P6 — Gói thu thập thủ công có kiểm soát V1

## Tên bước và ý nghĩa

**P6: chuẩn bị packet thu thập thủ công.** Bước này biến các ghi chú rời rạc về
DFPI, SSC Việt Nam và HNX thành một hợp đồng nộp file có thể kiểm tra bằng máy.
Nó không tải dữ liệu, không mở nguồn bị chặn, không truy cập domain ứng viên,
không tạo candidate/label và không mở dữ liệu validation/test.

## Bạn cần làm gì khi quay lại bước thủ công

### DFPI Crypto Scam Tracker

1. Dùng trình duyệt thông thường và chỉ tiếp tục nếu trang cho phép truy cập;
   không vượt Cloudflare hoặc cơ chế kiểm soát truy cập.
2. Ưu tiên first-party download/export. Nếu không có, chỉ lưu artifact mà trình
   duyệt hợp lệ của bạn hiển thị cho mục đích nghiên cứu nội bộ.
3. Lưu nguyên file, không sửa, tối đa 20 file mỗi submission, vào:
   `D:\nckh 2026-2027\ISI_Data\raw\dfpi_crypto_scam_tracker\YYYY-MM-DD\`.
4. Tạo manifest từ template, ghi URL, thời điểm, tên gốc, media type, số byte,
   SHA-256, điều kiện sử dụng và cờ dữ liệu cá nhân.
5. Complaint DFPI luôn bắt đầu là `UNCERTAIN`. Nội dung complaint không phải
   input model; muốn đề xuất `CONFIRMED` vẫn cần bằng chứng chính thức độc lập
   và một artifact đầu tư quan sát được riêng biệt.

### SSC Việt Nam — cảnh báo nhà đầu tư

Chưa tải record. Trước hết phải có một trong hai thứ: export/download chính
thức với điều kiện sử dụng rõ ràng, hoặc văn bản cho phép sử dụng nội bộ cho
nghiên cứu. Sau khi bằng chứng quyền sử dụng được lưu và kiểm tra độc lập, một
release mới mới được phép thu thập. Không tự scrape, không lưu cả bundle trang,
không coi cảnh báo là nhãn `CONFIRMED` tự động.

Đích dự kiến sau khi gate quyền sử dụng mở:
`D:\nckh 2026-2027\ISI_Data\raw\ssc_vietnam_investor_warnings\YYYY-MM-DD\`.

### HNX — hồ sơ tổ chức niêm yết

Chưa tải record. Cũng cần export/download chính thức hoặc văn bản cho phép sử
dụng nội bộ trước. Chỉ giữ artifact được phép và provenance tối thiểu; không
phát hành lại bundle dữ liệu HNX. Một hồ sơ niêm yết chỉ hỗ trợ đối chiếu danh
tính/domain, không tự chứng minh website hoặc nội dung là `LEGITIMATE`.

Đích dự kiến sau khi gate quyền sử dụng mở:
`D:\nckh 2026-2027\ISI_Data\raw\hnx_vietnam_issuer_profiles\YYYY-MM-DD\`.

## Manifest và kiểm tra

Template nằm tại
`registry/pilots/target_text_manual_acquisition_submission_template_v1.json`.
Sao chép template ra ngoài Git, thay toàn bộ giá trị mẫu, bỏ `template_id` và
`instructions`, rồi đặt status là `PENDING_INDEPENDENT_INTAKE_QA`. Không commit
file nguồn, dữ liệu cá nhân hoặc thư cho phép vào repository công khai.

Sau khi có file DFPI hợp lệ, kiểm tra bằng:

```powershell
.venv\Scripts\python.exe -m scripts.verify_target_text_corpus_v1_manual_acquisition_packet_v1 `
  --packet configs\target_text_corpus_v1_manual_acquisition_packet_v1.json `
  --submission "D:\nckh 2026-2027\ISI_Data\governance\target_text_corpus_v1\manual_submission_v1.json" `
  --raw-root "D:\nckh 2026-2027\ISI_Data\raw"
```

Validator kiểm tra allowlist host, acquisition mode, quyền sử dụng, thư mục,
kích thước và SHA-256. Kết quả pass chỉ có nghĩa là file đủ điều kiện vào QA;
không tạo candidate, nhãn, quota hay quyền đưa vào model.

## Trình tự sau khi nhận file

1. QA độc lập bytes/hash/source/quyền sử dụng/dữ liệu cá nhân.
2. Đăng ký kết quả intake bất biến, không đưa nội dung được bảo hộ vào Git.
3. Nếu nhận SSC/HNX làm channel, đóng băng Sampling Matrix V2 trước enumeration.
4. Tạo release hash-bound riêng cho enumeration/capture.
5. Thu một archived observed investment artifact riêng; text chính thức không
   phải text model.
6. Grouping, primary review, blind second review, reconciliation và owner
   acceptance.

Cho đến khi chuỗi gate trên hoàn tất, cả ba nguồn đều không đóng góp bản ghi
training đủ điều kiện.
