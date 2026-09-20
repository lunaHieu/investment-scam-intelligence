# Financial Claims V2 trên Mendeley group split

## Kết luận

V2 là bản sửa có kiểm soát của Financial Claims V1. Sáu dương tính giả trong
pilot 43 review unit đã được người dùng xác nhận theo quy trình có AI hỗ trợ và
được chuyển thành năm bộ lọc ngữ cảnh. Đây vẫn là candidate feature set, không
phải model và không phải nhãn scam.

## Phạm vi và chống leakage

- Đầu vào giữ nguyên SHA-256
  `0f540f838dc0050c2cc1f8f8d98c4239acaba1ad0d1407066f1a578e5acdb2ff`.
- Chỉ xử lý 11.344 train và 2.429 validation, tổng 13.773 record.
- Bỏ qua 2.429 record test; nội dung test được xử lý bằng 0.
- Không dùng hoặc phát ra source label; không gọi mạng; không sửa raw.
- V1 vẫn tái lập được và giữ nguyên rule hash. V2 có rule-set hash riêng:
  `e462fae5e77320bd5c50c38d56e3068248c86cc177bac7d17bc30314d6fef71a`.

## Các sửa đổi V2

1. Không coi `double-digit` hoặc `triple-digit` là lợi nhuận dạng `Nx`.
2. Không coi phần trăm mô tả `discount` là tỷ suất lợi nhuận.
3. Loại thuật ngữ `risk-free rate` và câu biểu mẫu `no risk or obligations`
   khỏi tín hiệu không rủi ro.
4. Loại câu phủ định `not a get rich quick ...` khỏi tín hiệu thu nhập dễ dàng.
5. Loại chỉ dẫn phủ định như `do not send ...` khỏi yêu cầu chuyển tài sản.

Sáu signal assignment sai đã biến mất đúng như kỳ vọng: một `RETURN_RATE`, một
`RETURN_MULTIPLE`, hai `NO_RISK`, một `PASSIVE_OR_EASY_INCOME` và một
`PAYMENT_OR_TRANSFER_REQUEST`. Các unit đúng trong pilot vẫn được giữ.

## Profile V2

| Tín hiệu | V1 | V2 | Chênh lệch |
| --- | ---: | ---: | ---: |
| RETURN_RATE | 48 | 47 | -1 |
| RETURN_MULTIPLE | 388 | 387 | -1 |
| MONEY_AMOUNT | 6.462 | 6.462 | 0 |
| GUARANTEED_RETURN | 19 | 19 | 0 |
| NO_RISK | 26 | 24 | -2 |
| URGENCY_SCARCITY | 651 | 651 | 0 |
| PASSIVE_OR_EASY_INCOME | 1.056 | 1.055 | -1 |
| RECRUITMENT_REWARD | 1 | 1 | 0 |
| PAYMENT_OR_TRANSFER_REQUEST | 4 | 3 | -1 |
| ADVANCE_FEE_OR_WITHDRAWAL | 0 | 0 | 0 |
| CRYPTO_INVESTMENT_OR_PAYMENT | 883 | 883 | 0 |

Có 7.512 record khớp ít nhất một tín hiệu, giảm một record so với V1. Con số
này không phải tỷ lệ lừa đảo.

## Kiểm tra và trạng thái

- Recompute toàn bộ 13.773 output từ CSV nguồn khớp hoàn toàn.
- Queue mới có 120 record thuộc 120 group khác nhau: 80 signal candidate và 40
  no-signal audit; tất cả là `UNREVIEWED`.
- Test tự động bao phủ cả sáu lỗi đã xác nhận và năm ví dụ dương tính cần giữ.
- Training gate vẫn đóng vì pilot ban đầu có AI hỗ trợ, queue V2 chưa được
  review độc lập và no-signal audit chưa hoàn tất.

Bước tiếp theo là review queue V2 trên train/validation. Chỉ sau khi tổng hợp
được precision theo từng signal và false negative trong no-signal audit mới
xem xét đóng băng feature set cho thí nghiệm model; test vẫn tiếp tục giữ kín.

## Workbook review V2

Workbook review V2 được tạo tại
`D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\financial_claims_v2\ISI_Financial_Claims_V2_Review.xlsx`.
SHA-256 là
`b73bd091abe8281c5b9492f46db26b03419c6cb9b139ccbdb7e03fef24067bd2`.

Pilot V2 có 30 record: 20 signal candidates đầu queue và 10 no-signal audit
đầu tiên. Chúng tạo thành 52 review unit. AI tạm đề xuất:

- 38 `CORRECT` và 4 `INCORRECT` cho các signal đã phát hiện.
- 10 `NO_MISSED_SIGNAL` cho nhóm no-signal.
- 0 `UNCERTAIN` và 0 `MISSED_SIGNAL` trong 10 no-signal record.

Ngoài outcome theo từng unit, AI ghi riêng 5 record có khả năng bị thiếu signal.
Các trường hợp này gồm `riskfree curve`, khoảng cách giữa crypto và claim `Nx`,
NFT chưa có trong asset cues, và cấu trúc `Turn $500 into $5000`.

Workbook lấy evidence trực tiếp theo từng `target_signal` từ feature records,
thay vì chỉ dùng năm context đầu của queue. Gợi ý AI chưa làm thay đổi
`completion_status`; toàn bộ cột quyết định người review vẫn trống. Training
gate và test tiếp tục đóng cho đến khi người dùng xác nhận hoặc sửa pilot này.

## Xác nhận ngày 2026-09-20

Người dùng đã đọc và chấp thuận toàn bộ 52 gợi ý trong pilot, không có override.
Workbook xác nhận được lưu với tên
`ISI_Financial_Claims_V2_Review_Confirmed.xlsx`; 52 review unit có
`completion_status = HOÀN TẤT`. Đây là xác nhận có AI hỗ trợ, không phải blind
review độc lập và không phải nhãn scam. Bốn false positive cùng năm coverage
finding đã được dùng làm cơ sở có kiểm soát cho Financial Claims V3; test và
training gate vẫn đóng.
