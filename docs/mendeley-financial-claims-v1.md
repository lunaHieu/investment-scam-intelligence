# Financial Claims V1 trên Mendeley group split

## Kết luận

Đã tạo bộ trích xuất quy tắc song ngữ có thể giải thích cho các dấu hiệu tài
chính trong `text_content`. Đây là **candidate feature set**, chưa phải model và
không phải kết luận lừa đảo.

Các nhóm tín hiệu dựa trên những dấu hiệu thường được cơ quan bảo vệ nhà đầu tư
nêu ra: lợi nhuận cao/được bảo đảm, ít hoặc không có rủi ro, gây áp lực phải
hành động ngay và yêu cầu chuyển tài sản. Nguồn phương pháp:
[Investor.gov](https://www.investor.gov/protect-your-investments/fraud/protect-your-money),
[SEC red-flags checklist](https://www.investor.gov/protect-your-investments/fraud/how-avoid-fraud/red-flags-investment-fraud-checklist),
[FTC investment scams](https://consumer.ftc.gov/articles/investment-scams) và
[FTC cryptocurrency scams](https://consumer.ftc.gov/articles/what-know-about-cryptocurrency-scams).

## Phạm vi chống leakage

- Đầu vào là Mendeley `group_split_v1`, đã giữ duplicate/template group trong
  cùng partition.
- Chỉ xử lý 11.344 train và 2.429 validation, tổng 13.773 record.
- Không xử lý nội dung của 2.429 record test.
- Không dùng source label để quyết định signal và không ghi label vào output.
- `partition` và `split_group_id` chỉ là provenance ngoài container `features`.
- Không gọi mạng và không thay đổi raw.

## Các tín hiệu V1

1. Tỷ suất lợi nhuận có phần trăm.
2. Lợi nhuận dạng nhân nhiều lần như `10x` hoặc `100x`.
3. Số tiền có đơn vị tiền tệ.
4. Cam kết lợi nhuận chắc chắn.
5. Không có rủi ro hoặc không thể thua lỗ.
6. Gây khẩn cấp hoặc khan hiếm.
7. Thu nhập thụ động, dễ dàng hoặc làm giàu nhanh.
8. Thưởng/hoa hồng gắn với tuyển hoặc giới thiệu người.
9. Yêu cầu gửi, chuyển hoặc nạp tài sản.
10. Phí/thuế gắn với mở khóa hoặc rút tiền.
11. Crypto gắn với đầu tư, thanh toán, chuyển tiền hoặc lợi nhuận.

Mỗi lần khớp giữ `rule_id`, loại tín hiệu, vị trí ký tự, đoạn khớp và ngữ cảnh
ngắn. Nhờ vậy reviewer có thể nhìn thấy lý do, thay vì chỉ nhận một điểm số.

## Profile train/validation

| Tín hiệu | Số record |
| --- | ---: |
| Số tiền | 6.462 |
| Thu nhập thụ động/dễ dàng | 1.056 |
| Crypto gắn với đầu tư/thanh toán | 883 |
| Khẩn cấp/khan hiếm | 651 |
| Lợi nhuận dạng `Nx` | 388 |
| Tỷ suất lợi nhuận | 48 |
| Không rủi ro | 26 |
| Cam kết lợi nhuận | 19 |
| Yêu cầu chuyển tiền/tài sản | 4 |
| Thưởng tuyển/giới thiệu | 1 |
| Phí mở khóa/rút tiền | 0 |

Có 7.513 record, tương đương 54,55%, khớp ít nhất một tín hiệu. Con số cao chủ
yếu do 6.462 record có số tiền; **không được diễn giải thành 54,55% record là
lừa đảo hoặc có claim sai**. `MONEY_AMOUNT` là trích xuất trung tính.

## Kiểm tra lỗi đã thực hiện

Các test biên đã loại ba false positive được phát hiện trong lần chạy thử:

- `66% interest in a subsidiary` không còn bị coi là tỷ suất sinh lời.
- `release tax returns` không còn bị coi là phí để rút tiền.
- `refer the issue to a commission` không còn bị coi là hoa hồng tuyển người.

Bộ test cũng bao phủ ví dụ Anh/Việt, tỷ lệ phần trăm trung tính, lợi nhuận
crypto dạng `1000x`, yêu cầu chuyển crypto và cổng giữ test nguyên vẹn.

## Review queue 120

- 80 signal candidates, lấy luân phiên giữa các loại tín hiệu.
- 40 no-signal records để tìm dấu hiệu bị bỏ sót.
- 120 record thuộc 120 `split_group_id` khác nhau.
- Tất cả giữ trạng thái `UNREVIEWED`.

Queue chưa được gán nhãn. Trước khi dùng feature để train, reviewer phải đánh
giá độ đúng theo từng signal và xem nhóm no-signal có bỏ sót gì hay không.

## Workbook review

Workbook review đã được tạo tại
`D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\financial_claims_v1\ISI_Financial_Claims_V1_Review.xlsx`.
SHA-256 của workbook là
`97a0a81c39ec0554e4d9ab9c767195d464c3bb44fea433ff29a7ef0f98d9e153`.

- Sheet `Tong quan` giải thích mục tiêu, outcome và tiến độ.
- Sheet `Danh gia` là nơi nhập review duy nhất. 120 record được tách thành 203
  review unit để mỗi signal có quyết định độc lập; 20 record đầu tương ứng 43
  review unit `PILOT_20`.
- Sheet `Nguon 120` giữ đủ 120 record nguồn để đối chiếu.
- Các cột màu vàng là cột nhập. `completion_status` chỉ chuyển thành
  `HOÀN TẤT` khi outcome hợp lệ và đủ các trường bắt buộc.
- Việc review chỉ đánh giá rule. Không gán nhãn scam và không mở test.

Registry kiểm toán của workbook nằm tại
`registry/analyses/mendeley_financial_claims_review_workbook_v1.json`.

## Quyết định

Feature set được đóng băng ở trạng thái
`FROZEN_CANDIDATE_FEATURES_REVIEW_REQUIRED`. Training gate vẫn đóng. Việc cần
làm tiếp theo là hoàn thành pilot 20 record trong workbook, kiểm tra tính rõ
ràng của protocol rồi mới review phần còn lại. Không được gọi Financial Claims
V1 là đã được xác thực trước khi review hoàn tất và được tổng hợp.
