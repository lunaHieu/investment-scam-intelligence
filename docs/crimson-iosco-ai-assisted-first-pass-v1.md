# Crimson IOSCO AI-assisted first pass V1

## Kết quả

Toàn bộ 32 IOSCO match trong pilot đã có first pass dựa trên 53 record I-SCAN.
Có 30 host được đề xuất `SAME_ENTITY`; hai host được đề xuất
`IMPERSONATION_SUSPECTED`: `passinvestmentmanagers.com` và `benefittrade.org`.
Mọi trường hợp đều giữ `WARNING_RELEVANT`, `IN_PROGRESS`,
`training_eligible = NO` và `label_created = false`.

Hai mươi host dùng reference host xuất hiện trong nhiều record. Cộng thêm trường
hợp `benefittrade.org` có dấu hiệu imposter, tổng cộng 21 host đã được đặt
`second_review_status = REQUESTED`.

## Kiểm tra URL cảnh báo

41 URL chính thức đã được kiểm tra read-only, không mở domain Crimson:

- 16 host có toàn bộ URL sống xác nhận được.
- 9 host xác nhận được một phần: `bitforex.com`, `aiminingex.com`,
  `chainstackinvest.com`, `opentrading-platform.com`,
  `passinvestmentmanagers.com`, `primewealthltd.com`, `affiliate.primexbt.com`,
  `me.tradextixcoins.com`, `www-stage.cedarfx.com`.
- 7 host hiện chỉ dựa vào snapshot I-SCAN vì mọi URL sống đều bị chặn hoặc không
  phản hồi: `cryptobanxatrade.com`, `forexcapitalgain.com`,
  `magnomicyieldltd.com`, `virtualcapitaltraders.com`, `hotfxcrypto.net`,
  `banktrustcoin.com`, `benefittrade.org`.

Các URL không render được được giữ lại cho kiểm tra thủ công sau. Điều này không
làm mất hiệu lực của record I-SCAN đã khóa hash, nhưng không được mô tả như đã
xác nhận trực tiếp trên trang sống.

## Kiểm soát

- Không truy cập trực tiếp bất kỳ domain Crimson nào.
- Warning là bằng chứng của cơ quan quản lý, không phải bản án hoặc nhãn scam tự
  động.
- Workbook giữ riêng trạng thái snapshot, live URL check, quan hệ danh tính và
  yêu cầu second review.
- Chỉ người review mới được chuyển `IN_PROGRESS` sang `COMPLETED`.
