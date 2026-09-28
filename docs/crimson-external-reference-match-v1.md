# Đối chiếu Crimson với nguồn chính thức — V1

## Kết luận

Đã đối chiếu ngoại tuyến 43.572 artifact Crimson với chỉ mục cảnh báo IOSCO và
chỉ mục đăng ký SEC/IAPD. Sau khi chỉ chuẩn hóa tiền tố `www.`, 43.572 artifact
tương ứng 43.487 canonical host. Có 345 artifact, thuộc 344 canonical host, có
ít nhất một tham chiếu nguồn chính thức.

Đây là **hàng đợi bằng chứng**, không phải nhãn huấn luyện:

- IOSCO match là bằng chứng có cảnh báo cần review, không phải bản án.
- SEC match là tham chiếu đăng ký cần kiểm tra mạo danh, không phải bằng chứng
  website an toàn hoặc thực sự do công ty đã đăng ký vận hành.
- Không match chỉ có nghĩa là không tìm thấy trong hai snapshot hiện tại; không
  có nghĩa là an toàn.

## Kết quả

| Nhóm review | Canonical host |
| --- | ---: |
| IOSCO exact host | 298 |
| IOSCO host hierarchy | 38 |
| SEC exact host | 6 |
| SEC host hierarchy | 2 |
| Đồng thời IOSCO và SEC | 0 |
| **Tổng queue** | **344** |

Có 370 cặp artifact–reference: 362 từ IOSCO và 8 từ SEC. Trong đó 322 cặp là
exact host, 47 cặp là Crimson subdomain của host tham chiếu và 1 cặp là chiều
ngược lại. Có 49 cặp dùng host tham chiếu xuất hiện trong nhiều record nguồn;
chúng được giữ nguyên và đánh dấu để review, không tự gộp thực thể.

## Kiểm soát sai lệch

- Đối chiếu chỉ dùng chuỗi hostname; không DNS, HTTP, WHOIS, TLS hay truy cập web.
- Không suy luận public suffix hoặc registrable domain.
- Quan hệ subdomain chỉ là candidate relation, không phải same-entity assertion.
- 85 cặp artifact Crimson khác nhau do tiền tố `www.` vẫn được giữ provenance;
  queue nhóm theo canonical host để tránh review lặp.
- Mọi record vẫn `UNREVIEWED`, `identity_resolved=false`, `label_created=false`.

## Artifact đã khóa

- `reference_matches_v1.jsonl`: 370 record, SHA-256
  `bd1a58555b78b07653406756a5211bdb3b5d95102e19b8487bf7577b2669eead`.
- `review_queue_v1.jsonl`: 344 record, SHA-256
  `d73be96ef20ec6867458134b0ab56d2327de4a4be8bb70b9b3b01efa338defd1`.
- `match_report_v1.json`: SHA-256
  `7ffdb3b5124bb7fb30e96c406e838825c8103f3a8eebcc72a6fc61d4c11e79d1`.

Hai output JSONL đã được dựng lại trong thư mục tạm và cho SHA-256 giống hệt,
xác nhận kết quả có tính tái lập.

## Bước kế tiếp

Tạo một pilot review nhỏ, ưu tiên toàn bộ 8 SEC match, các IOSCO match có nhiều
record cảnh báo và một mẫu quan hệ subdomain. Review chỉ dựa trên snapshot và
đường dẫn cơ quan quản lý; không mở trực tiếp domain Crimson.
