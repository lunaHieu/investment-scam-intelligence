# Financial Claims V3 trên Mendeley group split

## Kết luận

V3 áp dụng các quyết định đã được người dùng xác nhận trong pilot V2 có AI hỗ
trợ. Bốn dương tính giả được chuyển thành bộ lọc ngữ cảnh, còn năm record có
khả năng bị bỏ sót được bao phủ bằng bốn rule mới. V3 vẫn là candidate feature
set, không phải nhãn scam và chưa được phép dùng để huấn luyện.

## Phạm vi và chống leakage

- Đầu vào giữ nguyên SHA-256
  `0f540f838dc0050c2cc1f8f8d98c4239acaba1ad0d1407066f1a578e5acdb2ff`.
- Chỉ xử lý 11.344 train và 2.429 validation, tổng 13.773 record.
- Bỏ qua 2.429 record test; nội dung test được xử lý bằng 0.
- Không dùng source label, không gọi mạng và không sửa raw.
- Rule-set SHA-256 của V3 là
  `1ab63dde22f35083772eafd8f3bcde344ffe95d3c3e91c2f8d326646c830bd11`.

## Thay đổi từ V2

Các bộ lọc mới loại:

1. Phần trăm `working interest` khỏi `RETURN_RATE`.
2. Bảo lãnh của chính phủ hoặc hợp đồng khỏi `GUARANTEED_RETURN`.
3. Chính sách hoàn tiền sản phẩm khỏi `NO_RISK`.
4. Thuật ngữ `riskfree curve` khỏi `NO_RISK`.

Các rule mới phát hiện:

1. Crypto hoặc NFT đi cùng động từ tăng giá và mức `Nx` trong cửa sổ có giới hạn.
2. Cấu trúc `Turn $500 into $5000`, nhưng không nhận trường hợp số sau bằng
   hoặc nhỏ hơn số trước.
3. Khoản tiền đã kiếm được gắn với hệ thống Bitcoin, crypto hoặc NFT.
4. NFT trong đúng hai ngữ cảnh tăng giá và kiếm tiền mới; không mở rộng tùy ý
   sang mọi chỗ có chữ NFT.

## Kết quả tái lập

| Tín hiệu | V2 | V3 | Chênh lệch record |
| --- | ---: | ---: | ---: |
| RETURN_RATE | 47 | 43 | -4 |
| RETURN_MULTIPLE | 387 | 1.509 | +1.122 |
| MONEY_AMOUNT | 6.462 | 6.462 | 0 |
| GUARANTEED_RETURN | 19 | 17 | -2 |
| NO_RISK | 24 | 22 | -2 |
| URGENCY_SCARCITY | 651 | 651 | 0 |
| PASSIVE_OR_EASY_INCOME | 1.055 | 1.055 | 0 |
| RECRUITMENT_REWARD | 1 | 1 | 0 |
| PAYMENT_OR_TRANSFER_REQUEST | 3 | 3 | 0 |
| ADVANCE_FEE_OR_WITHDRAWAL | 0 | 0 | 0 |
| CRYPTO_INVESTMENT_OR_PAYMENT | 883 | 2.509 | +1.626 |

V3 có 7.511 record khớp ít nhất một tín hiệu. Số record candidate giảm một vì
các record mới được bổ sung tín hiệu phần lớn đã có tín hiệu khác, trong khi
một record chỉ chứa false positive đã bị loại. Mức tăng lớn ở hai tín hiệu mới
chủ yếu đến từ các mẫu bài đăng tổng hợp lặp lại; chưa được coi là precision đã
xác nhận.

## Kiểm tra pilot đã xác nhận

- 52/52 review unit V2 đã được người dùng chấp thuận theo quy trình có AI hỗ trợ.
- Bốn false positive mục tiêu không còn trong V3.
- Cả năm record coverage finding đều nhận đủ tín hiệu được kỳ vọng.
- Ba record `working interest` lặp lại và một record government guarantee lặp
  lại cũng được loại đúng theo cùng ngữ cảnh.
- Test đơn vị chặn số tiền không tăng trong cấu trúc `Turn A into B` và không
  coi `stock` là crypto trong rule earnings mới.

## Trạng thái

Feature records, profile và queue 120 record của V3 đã được tái lập và xác minh
hash trên ổ D. Queue gồm 80 signal candidate và 40 no-signal audit, mỗi record
thuộc một split group riêng và vẫn hoàn toàn `UNREVIEWED`.

Training gate vẫn đóng. Bước tiếp theo là review có chủ đích các match tăng thêm
của từng rule V3 và no-signal audit trên train/validation. Test tiếp tục được giữ
kín cho đến khi cấu hình cuối được đóng băng.

## Pilot kiểm định V3 đã tạo

Workbook `ISI_Financial_Claims_V3_Review.xlsx` chọn có chủ đích 20 record, tạo
44 review unit:

- 15 signal candidate bao phủ cả bốn rule mới;
- 5 no-signal audit ưu tiên các trường hợp giàu thông tin;
- 39 review unit tín hiệu và 5 review unit no-signal;
- 44/44 unit có gợi ý AI, nhưng mọi cột quyết định của người review vẫn trống.

Gợi ý AI sơ bộ gồm 36 `CORRECT`, 3 `INCORRECT`, 2 `NO_MISSED_SIGNAL` và 3
`MISSED_SIGNAL`. Ba gán nhầm cùng nằm trong email `spam_email_489`: claim
`Turn $2 into $5` bị phủ định, `no risk` nằm trong câu loại trừ, và các phần trăm
là phân bố thu nhập chứ không phải tỷ suất lợi nhuận. Ba no-signal record cần
kiểm tra lại liên quan đến emoji tên lửa với mức `Nx`, urgency, và annuity rate
được bảo đảm.

Các tỷ lệ sơ bộ theo rule V3 chỉ là đề xuất AI trên mẫu chọn có chủ đích:

| Rule V3 | AI đề xuất đúng | Mẫu kiểm tra |
| --- | ---: | ---: |
| `FCV3_RETURN_MULTIPLE_TURN_01` | 5 | 6 |
| `FCV3_RETURN_MULTIPLE_GROWTH_01` | 5 | 5 |
| `FCV3_CRYPTO_GROWTH_01` | 5 | 5 |
| `FCV3_CRYPTO_EARNINGS_01` | 4 | 4 |

Không con số nào ở trên được coi là precision chính thức trước khi người dùng
xác nhận từng dòng. Training gate vì vậy vẫn đóng; bước kế tiếp là human
confirmation rồi mới sửa rule thành V4 nếu các lỗi được chấp thuận.

Ngày 2026-09-20, người dùng đã chấp thuận toàn bộ 44/44 gợi ý theo quy trình
`AI_ASSISTED_HUMAN_CONFIRMATION`, không phải blind review và không có override.
Bản workbook xác nhận cùng hồ sơ xác nhận đã được lưu cạnh artifact V3 trên ổ D.
Ba lỗi và ba coverage finding đã được chuyển thành V4; training gate của V3
được thay bằng yêu cầu review gia tăng của V4.

Lưu ý audit: trong lúc tra cứu một record train theo tiền tố ID, lệnh tìm kiếm đã
hiển thị ngoài ý muốn một dòng từng thuộc test của `group_split_v1`. Dòng này đã
được chuyển sang `auxiliary` trong `group_split_v2`, không nằm trong pilot và
không được dùng để sửa rule hay huấn luyện. Tập test hiện hành của
`group_split_v2` vẫn chưa được mở.
