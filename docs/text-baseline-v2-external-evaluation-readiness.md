# External evaluation readiness cho Text Baseline V2

## Kết luận

Chưa được phép chạy external evaluation. Hiện có **0 mẫu text external đủ điều kiện**, nên hệ thống không tạo score và không báo metric.

Đây là chặn đúng theo phương pháp nghiên cứu, không phải lỗi kỹ thuật. Nếu dùng bài cảnh báo, complaint hoặc domain chưa review làm test binary, kết quả sẽ đo sai đối tượng và không còn ý nghĩa.

## Những gì đã kiểm tra

| Nguồn | Hiện có | Text quan sát được | Evidence/review đủ điều kiện | Có thể chấm model |
| --- | ---: | ---: | ---: | --- |
| Crimson raw | 43.572 URL/network/IOC records | 0 | Không áp dụng | Không |
| Crimson review workbook | 100 candidate domains | 0 | 0; toàn bộ `UNREVIEWED` | Không |
| UBCKNN pilot | 5 warning documents | 0 | 5 case đều `UNCERTAIN` | Không |
| DFPI | Chỉ có template | 0 | 0 | Không |
| SEC IAPD | Chưa có raw reference | Không phải content source | 0 | Không |
| IOSCO I-SCAN | Chưa có export | 0 | 0 | Không |

Crimson raw chỉ có các trường `url`, `isp`, `ioc`, `query`, `countryCode`, `region`, `eth` và `btc`. Nó không chứa page text, HTML hay OCR. Workbook Crimson vẫn có 100/100 dòng `UNREVIEWED`; các trường ground truth, evidence URL và rationale đều trống.

UBCKNN là evidence cấp case. Các trang cảnh báo không được dùng như positive solicitation text, nhất là khi artifact hiện không lưu nội dung và case vẫn `UNCERTAIN`.

## Policy đã đóng băng

Policy nằm tại `configs/text_baseline_v2_external_eval_policy_v1.json`. Một record chỉ được vào external text pilot khi đáp ứng toàn bộ điều kiện:

- nguồn nằm ngoài Mendeley;
- `ground_truth_status` là `CONFIRMED` hoặc `LEGITIMATE`;
- `label_confidence = HIGH`;
- `review_status = RECONCILED`;
- artifact là `POST`, `MESSAGE` hoặc `WEBSITE_SNAPSHOT`;
- có text quan sát được tối thiểu 20 ký tự không phải khoảng trắng;
- có evidence đã review, hỗ trợ đúng `SCAM_CLAIM` hoặc `LEGITIMACY`;
- có case/campaign group và near-duplicate group để chống leakage.

`WARNING_DOCUMENT` và `COMPLAINT` bị loại khỏi input text của model vì chúng mô tả vụ việc, không phải nội dung solicitation mà hệ thống cần phân loại.

Pilot chỉ được báo metric khi có tối thiểu 20 mẫu: ít nhất 10 `CONFIRMED` và 10 `LEGITIMATE`. Đây vẫn chỉ là pilot nhỏ, không đủ cho tuyên bố deployment hay hiệu năng tổng quát.

## Những việc đang chờ thao tác thủ công

1. Tải hợp lệ DFPI export/raw nếu tài khoản/trình duyệt của bạn truy cập được.
2. Tải SEC IAPD/Form ADV snapshot chính thức để làm evidence tham chiếu entity hợp pháp.
3. Tải IOSCO I-SCAN CSV export nếu dùng nguồn này.
4. Review Crimson bằng evidence độc lập. Không để pipeline tự mở candidate URL.
5. Thu thập chính nội dung post/message/website snapshot có provenance; URL hoặc warning page một mình chưa đủ.

Sau khi có tệp, lưu bản gốc vào `D:\nckh 2026-2027\ISI_Data\raw\<source_id>\<date>\` và báo đường dẫn. Pipeline sẽ hash, kiểm tra cấu trúc, giữ nguyên provenance rồi chạy lại gate.

## Kiểm tra tái lập

Report chính thức:

`D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_baseline_v2\external_eval_readiness_v1\external_evaluation_readiness_report_v1.json`

SHA-256: `d946c83189c0a3de1335e3cb09ed0025b41b3b8f479b583a17195c90821088de`

Chạy verifier:

```powershell
.venv\Scripts\python.exe scripts\verify_text_baseline_v2_external_readiness_registry.py
```

Audit hoàn toàn offline: không mở domain, không sửa workbook, không tạo nhãn, không fit hoặc score model.
