# Curated Evidence Pilot (DFPI + SEC)

## Mục tiêu

Pilot này tạo một tập nhỏ, truy vết được nguồn gốc, để kiểm tra cách nối
`artifact` (nội dung/URL) với `evidence` (bằng chứng). Nó **không** phải là
tập để tự động kết luận một website hay tổ chức là lừa đảo.

## Hai nguồn và vai trò

| Nguồn | Dùng để làm gì | Không được suy ra |
| --- | --- | --- |
| DFPI Crypto Scam Tracker | Seed từ phản ánh người dùng: narrative, scam type, website, screenshot | Một phản ánh đơn lẻ = `CONFIRMED` |
| SEC Form ADV / IAPD | Đối chiếu một tổ chức có hồ sơ đăng ký tư vấn đầu tư | Có đăng ký = mọi nội dung/URL liên quan đều an toàn |

DFPI hiện yêu cầu xác minh người dùng trên trang web. Không được vượt cơ chế
này hoặc tự động thu thập qua nó. Bất kỳ batch DFPI nào chỉ được nhập khi có
bản export/tải thủ công hợp lệ hoặc một nguồn công khai thay thế.

## Cách pilot vận hành

1. Lưu nguyên bản export/tệp được tải thủ công vào
   `D:\nckh 2026-2027\ISI_Data\raw\<source_id>\<YYYY-MM-DD>\`.
2. Ghi SHA-256 và URL nguồn vào manifest trước khi xử lý.
3. Chép **tối đa 20 case** vào `registry/pilots/dfpi_sec_curated_intake_template.json`
   hoặc một bản sao của nó. Không cần mở URL nghi vấn trên máy chính.
4. Mỗi complaint DFPI mới bắt đầu với `ground_truth_status: "UNCERTAIN"`.
   Một cảnh báo/quyết định độc lập có thể được liên kết thêm ở `evidence`.
5. SEC chỉ là evidence `official_registry`, dùng để đối chiếu danh tính;
   không biến nó thành nhãn cho nội dung.
6. Chạy `python scripts/validate_curated_intake.py --input <file>` trước khi
   đưa batch vào curated dataset.

## Việc của người nghiên cứu và việc AI hỗ trợ

- Người nghiên cứu: quyết định phạm vi, xác nhận nguồn tải thủ công có hợp lệ,
  và xem các case mà bằng chứng mâu thuẫn.
- AI: kiểm tra cấu trúc, tạo manifest, chuẩn hóa trường dữ liệu, phát hiện
  thiếu bằng chứng và lập báo cáo. AI không tự nâng `UNCERTAIN` thành
  `CONFIRMED`.

## Tiêu chí hoàn tất pilot

- Có 10--20 records có provenance.
- Mỗi record có ít nhất một evidence URL chính thức hoặc URL tracker gốc.
- Không record nào dùng "không thấy trong SEC" làm bằng chứng hợp pháp.
- Chỉ những artifact có nội dung/URL quan sát được mới trở thành ứng viên đầu
  vào của mô hình; văn bản cảnh báo không phải positive training text.

## Việc đang hoãn (cần thao tác thủ công hợp lệ)

| Nguồn | Trạng thái ngày 2026-09-11 | Việc cần làm sau này |
| --- | --- | --- |
| DFPI Crypto Scam Tracker | Trang yêu cầu Cloudflare xác minh người dùng. Chưa tải raw data. | Mở bằng trình duyệt thông thường, hoàn tất quyền truy cập hợp lệ của bạn (nếu có), sau đó lưu export/tệp công khai gốc vào kho raw. |
| SEC Form ADV / IAPD | SEC chặn tải tự động do request-rate threshold. Chưa tải raw data. | Tải thủ công ZIP tháng cần dùng từ trang SEC chính thức, rồi lưu nguyên bản vào kho raw. |

Sau khi có một trong hai tệp, chỉ cần báo mình tên/đường dẫn tệp; mình sẽ kiểm
tra hash, tạo manifest và đưa vào cổng intake. Không mở hay chạy URL nghi vấn
để lấy dữ liệu.
