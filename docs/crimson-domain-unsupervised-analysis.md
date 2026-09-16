# Phân tích không nhãn domain Crimson — V1

## Kết luận ngắn

Đã phân tích offline 43.572 domain bằng 23 lexical features. Bốn feature hằng
số bị loại, 19 feature còn lại được log-transform khi phù hợp, chuẩn hóa và
giảm xuống 9 thành phần PCA giữ 98,24% phương sai.

Trong sáu giá trị thử nghiệm, `k=4` có silhouette cao nhất (0,238). Tuy nhiên
độ ổn định giữa các seed thấp đến trung bình: ARI trung bình 0,427, thấp nhất
0,286. Vì vậy bốn cụm chỉ được dùng để lấy mẫu đa dạng, không được gọi là bốn
"loại lừa đảo" hay bốn loại domain ổn định.

## Kiểm soát an toàn

- Không truy cập domain, DNS, HTTP, WHOIS, certificate hay reputation service.
- Không tạo label và không train classifier.
- Chỉ dùng feature set `CRIMSON_URL_LEXICAL_V1` đã khóa hash.
- Review queue là hàng đợi ưu tiên xem xét, không phải danh sách kết luận scam.
- Không mở trực tiếp các domain trong queue trên máy chính.

## Chọn số cụm

| k | Silhouette ↑ | Davies–Bouldin ↓ | Calinski–Harabasz ↑ |
| ---: | ---: | ---: | ---: |
| 4 | **0,238** | **1,332** | **12.220** |
| 6 | 0,188 | 1,435 | 10.522 |
| 8 | 0,165 | 1,555 | 8.166 |
| 10 | 0,218 | 1,434 | 8.287 |
| 12 | 0,204 | 1,460 | 7.492 |
| 16 | 0,204 | 1,481 | 6.464 |

Silhouette 0,238 không thể hiện ranh giới cụm mạnh. `k=4` chỉ là phương án tốt
nhất trong tập ứng viên đã thử, không phải cấu trúc tự nhiên đã được chứng minh.

## Profile snapshot của bốn cụm

| Cụm | Records | Tỷ lệ | Đặc trưng tương đối nổi bật |
| ---: | ---: | ---: | --- |
| 0 | 14.236 | 32,7% | Domain và label ngắn hơn trung bình |
| 1 | 6.484 | 14,9% | Nhiều label/subdomain hơn, domain dài hơn |
| 2 | 20.887 | 47,9% | Ít subdomain hơn, phần tên chính dài hơn |
| 3 | 1.965 | 4,5% | Nhiều chữ số, digit run và chuyển tiếp chữ–số |

Các mô tả này là mean z-score của snapshot hiện tại. Do ARI thấp, một domain
có thể chuyển cụm khi thay seed; không dùng cluster ID như feature ground truth.

## Outlier ranking

Isolation Forest được chạy trên biểu diễn PCA với 300 cây và seed cố định.
436 domain nằm trong top 1% điểm bất thường cấu trúc; review queue chỉ lấy 50
domain đứng đầu. Điểm cao chỉ có nghĩa là khác thường so với các domain Crimson
khác, không có nghĩa là nguy hiểm hoặc lừa đảo hơn.

## Review queue 100

- 50 lexical outliers có anomaly score cao nhất.
- 50 domain gần tâm cụm nhất, phân bổ qua bốn cụm.
- 100 domain đều duy nhất và giữ trạng thái `UNREVIEWED`.

Queue dùng để sau này đối chiếu với nguồn chính thức hoặc chọn mẫu mô tả. Người
review không cần và không nên mở trực tiếp domain; việc xác minh phải đi qua
evidence/regulator sources hoặc snapshot được thu thập hợp lệ.

## Quyết định

Phân tích không nhãn đã hoàn thành đúng vai trò khám phá dữ liệu. Không có bằng
chứng đủ mạnh để xây taxonomy từ clustering. Bước có giá trị tiếp theo là có
lớp đối chứng độc lập và curated evidence; trước thời điểm đó, URL branch dừng
ở profiling và review-priority queue.
