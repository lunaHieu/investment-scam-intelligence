# Crimson URL intelligence — Feature Readiness V1

## Kết luận

Đã tạo một feature set lexical **không nhãn** cho toàn bộ 43.572 domain
Crimson. Mỗi feature được tính offline từ chuỗi domain; không domain nào được
truy cập. Feature set này sẵn sàng cho profiling, clustering và kiểm tra chất
lượng, nhưng **chưa đủ điều kiện train binary classifier** vì chưa có lớp URL
hợp pháp đối chứng độc lập.

## Lineage đã xác minh

| Tầng | Records | SHA-256 |
| --- | ---: | --- |
| Raw Crimson pinned commit | 43.572 | `5b6f5d8c...e313c0` |
| Candidate URL artifacts V2 | 43.572 | `75cb24ec...401ac` |
| URL lexical features V1 | 43.572 | `24831178...3a6c7` |

Raw có tám trường: `btc`, `countryCode`, `eth`, `ioc`, `isp`, `query`,
`region`, `url`. Chỉ domain đã chuẩn hóa từ `url` được dùng. Các trường còn lại
bị loại khỏi feature set vì có thể phản ánh cách thu thập hoặc nguồn dữ liệu,
không phải tín hiệu có thể quan sát công bằng ở runtime.

## Các kiểm tra đã đạt

- Raw SHA-256 khớp manifest và pinned commit.
- Candidate V2 có 43.572 artifact ID và 43.572 domain duy nhất.
- Validator tái tính toàn bộ feature của 43.572 records và khớp chính xác.
- Output không có trường label, evidence, ground truth hay metadata thu thập.
- Network operations: 0; không DNS, HTTP, WHOIS, TLS/certificate hay reputation lookup.
- Prefix `https://` trong candidate chỉ để hợp lệ schema, không được coi là dữ
  liệu quan sát và không được dùng làm feature.

## Profile mô tả

| Chỉ số | Min | P25 | Median | P75 | P95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Domain length | 7 | 16 | 19 | 23 | 36 | 81 |
| Label count | 2 | 2 | 2 | 2 | 3 | 9 |
| Digit ratio | 0 | 0 | 0 | 0 | 0 | 0,375 |
| Shannon entropy | 1,811 | 3,278 | 3,461 | 3,640 | 3,865 | 4,539 |

Tất cả domain đều ASCII; không có IP literal. Các số này chỉ mô tả Crimson,
không phải ngưỡng để kết luận domain đáng ngờ.

## Vì sao chưa train model URL

Nếu dùng toàn bộ Crimson làm lớp 1 rồi lấy một danh sách domain phổ biến làm
lớp 0, model có thể học khác biệt về thời gian, quốc gia, TLD hoặc quy trình
thu thập thay vì học dấu hiệu lừa đảo. Accuracy cao trong thiết kế đó sẽ không
đáng tin.

Trước khi train cần một lớp đối chứng có sampling frame tương thích, provenance
rõ ràng, loại trùng theo registrable domain/campaign và một external test có
evidence. SEC/DFPI đang nằm trong danh sách cần tải thủ công sau; SEC chỉ hỗ
trợ đối chiếu entity và không tự động trở thành nhãn URL an toàn.

## Bước kế tiếp không cần lớp đối chứng

Có thể dùng feature set này để kiểm tra phân bố, phát hiện outlier và tạo các
nhóm domain tương tự phục vụ review. Kết quả clustering/outlier chỉ là hàng đợi
ưu tiên review, không phải dự đoán lừa đảo.
