# Financial Claims V4 trên Mendeley group split

## Kết luận

V4 áp dụng 6 phát hiện đã được người dùng xác nhận trong pilot V3 có AI hỗ
trợ: loại ba dương tính giả trên một email dài và bổ sung ba nhóm tín hiệu bị
bỏ sót. V4 vẫn là candidate feature set, không phải nhãn scam và chưa được phép
dùng để huấn luyện.

## Phạm vi và chống leakage

- Đầu vào giữ nguyên SHA-256
  `0f540f838dc0050c2cc1f8f8d98c4239acaba1ad0d1407066f1a578e5acdb2ff`.
- Chỉ xử lý 11.344 train và 2.429 validation, tổng 13.773 record.
- Bỏ qua 2.429 record test; nội dung test được xử lý bằng 0.
- Không dùng source label, không gọi mạng và không sửa raw.
- Rule-set SHA-256 của V4 là
  `b992a0ee5ab657e30434730aeaf7194c98174b89039849a5a59b4a0f43328a01`.

## Thay đổi từ V3

Ba bộ lọc mới:

1. Loại cấu trúc `Turn A into B` khi câu phủ định khả năng đó.
2. Loại `no risk` khi văn bản dùng cụm này để từ chối hoặc đối chiếu với cơ hội
   đang quảng bá.
3. Loại phần trăm mô tả phân bố thu nhập khỏi `RETURN_RATE`.

Bốn rule mới:

1. Nhận mức `Nx` khi văn bản dùng emoji 🚀 thay cho động từ tăng giá.
2. Chỉ gán tín hiệu crypto cho mẫu trên khi tài sản thực sự là crypto hoặc NFT;
   từ `trading` đơn lẻ không bị coi là crypto.
3. Nhận urgency khi `ATTENTION` đi cùng lời kêu gọi `DM me`.
4. Nhận lãi suất được bảo đảm trong ngữ cảnh annuity có giới hạn.

## Kết quả tái lập

| Tín hiệu | V3 | V4 | Chênh lệch record |
| --- | ---: | ---: | ---: |
| RETURN_RATE | 43 | 42 | -1 |
| RETURN_MULTIPLE | 1.509 | 1.750 | +241 |
| MONEY_AMOUNT | 6.462 | 6.462 | 0 |
| GUARANTEED_RETURN | 17 | 18 | +1 |
| NO_RISK | 22 | 21 | -1 |
| URGENCY_SCARCITY | 651 | 1.274 | +623 |
| PASSIVE_OR_EASY_INCOME | 1.055 | 1.055 | 0 |
| RECRUITMENT_REWARD | 1 | 1 | 0 |
| PAYMENT_OR_TRANSFER_REQUEST | 3 | 3 | 0 |
| ADVANCE_FEE_OR_WITHDRAWAL | 0 | 0 | 0 |
| CRYPTO_INVESTMENT_OR_PAYMENT | 2.509 | 2.635 | +126 |

V4 có 7.754 record khớp ít nhất một tín hiệu, tăng 243 record so với V3. Mức
tăng lớn chủ yếu đến từ template tổng hợp lặp lại có `ATTENTION`, `DM me`, emoji
🚀 và mức `Nx`. Đây chưa phải bằng chứng precision cao.

## Kiểm tra hồi quy trên các phát hiện đã xác nhận

- `spam_email_489` chỉ còn `MONEY_AMOUNT`; ba gán nhầm đã bị loại.
- Mẫu NFT + 🚀 + 5x nhận `CRYPTO_INVESTMENT_OR_PAYMENT`, `RETURN_MULTIPLE` và
  `URGENCY_SCARCITY`.
- Mẫu trading + 🚀 + 10x nhận `RETURN_MULTIPLE` và `URGENCY_SCARCITY`, nhưng
  không bị coi là crypto.
- `phishing_5677` nhận `GUARANTEED_RETURN` trong ngữ cảnh annuity.
- Mortgage guarantee và bản tin cổ phiếu vẫn không nhận tín hiệu ngoài ý muốn.

## Gói pilot V4

Workbook pilot có chủ đích được tạo ngày 2026-09-20 từ queue V4 đã khóa. Ngày
2026-09-21, người dùng chấp nhận toàn bộ 37 gợi ý AI mà không override: 27 quyết
định `CORRECT` trên tín hiệu dương và 10 quyết định `NO_MISSED_SIGNAL` trên
no-signal audit. Đây là AI-assisted human confirmation, không phải blind review.

Pilot bao phủ cả bốn rule dương mới, gồm annuity và nhiều biến thể
rocket/attention. Ba post-filter mới đã có kiểm thử hồi quy tự động. Cả ba lỗi
thực tế là ba signal assignment trên cùng `spam_email_489`, không phải ba record.
Record này không nằm trong queue V4 tất định nên được kiểm tra riêng.

Spot-check ngày 2026-09-21 xác nhận V4 loại đúng `RETURN_MULTIPLE`, `NO_RISK` và
`RETURN_RATE` khỏi `spam_email_489`. Cả 12 match `MONEY_AMOUNT` được giữ nguyên.
So sánh toàn bộ 13.773 record cho thấy đây là record duy nhất bị loại khỏi từng
loại signal tương ứng. Workbook và gợi ý AI không phải nhãn train, nhãn scam,
ước lượng precision độc lập hoặc ước lượng recall.

## Trạng thái

Feature records, profile và queue 120 record của V4 đã được tái lập, kiểm tra
determinism và xác minh hash trên ổ D. Queue gồm 80 signal candidate và 40
no-signal audit, mỗi record thuộc một split group riêng. Queue nguồn vẫn giữ
`UNREVIEWED`; kết quả xác nhận được lưu riêng trong workbook và confirmation
package để không sửa artifact nguồn.

Pilot V4 đã được người dùng xác nhận theo quy trình có AI hỗ trợ và ba
post-filter đã qua spot-check. Rule set V4 được khóa. Ngày 2026-09-22, chính
rule set này đã được tái trích xuất trên train/validation của `group_split_v2`,
loại auxiliary, quarantine và không xử lý text test. Artifact `group_split_v1`
trong tài liệu này vẫn chỉ là lịch sử và không được ghép với baseline hiện hành.
Kết quả mới được mô tả tại `docs/mendeley-financial-claims-v4-group-split-v2.md`.
Một ablation đã khóa trước ngày 2026-09-23 không promote 11 cờ presence vào
baseline và không mở test; xem
`docs/mendeley-financial-claims-ablation-v1.md`.
