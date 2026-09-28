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
| DFPI | Chỉ có template; raw 0 file | 0 | 0 | Không |
| SEC IAPD | 23.927 firm reference đã xác minh | Không phải content source | 0 | Không |
| IOSCO I-SCAN | 47.001 warning reference đã xác minh | 0 | 0 | Không |
| Capture candidate queue V1 | 15 warning + 15 legitimate candidate | Queue, chưa phải artifact | 0; toàn bộ `UNCERTAIN` | Không |
| SEC legitimate capture pilots | 11 raw HTML (2 chính + 9 reserve) | 11 website snapshot đã trích text | 0; toàn bộ `UNCERTAIN + IN_REVIEW` | Không |
| SEC reserve queue V1 | 30 legitimate reserve candidate | 9/10 ứng viên đầu đã capture | 0; 9 AI first-pass recommendation, chưa có human confirmation | Không |

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

1. Review official reference trong capture candidate queue; warning không phải label.
2. Thu thập chính nội dung post/message/website snapshot có provenance; URL hoặc warning page một mình chưa đủ.
3. Với nhánh cảnh báo, ưu tiên historical/regulator-preserved artifact, không tự mở live suspicious domain.
4. Với nhánh hợp pháp, xác minh identity và exact registered host trước controlled capture.
5. Tải DFPI export/raw sau nếu trình duyệt cung cấp first-party export; không vượt Cloudflare.

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

## Cổng intake được bổ sung ngày 2026-09-23

Đã thêm template trống
`registry/pilots/external_text_evaluation_intake_template.json` và validator
`scripts/validate_external_text_intake.py`. Validator kiểm tra file capture và
SHA-256, exact text hash, evidence, human review status, case/campaign group,
near-duplicate group và ngưỡng 10 `CONFIRMED` + 10 `LEGITIMATE`. Nó không mở
URL hoặc tự tạo nhãn.

Sau snapshot ban đầu, SEC IAPD và IOSCO đã được tải, xác minh và lập reference
index. Tiếp đó hệ thống tạo hàng đợi dự phòng 30 ứng viên tại
`registry/pilots/external_text_capture_candidate_queue_v1.json`. Hai nguồn này
vẫn chỉ là evidence/reference, nên external text đủ điều kiện vẫn là 0. Hướng
dẫn thao tác nằm tại `docs/external-text-intake-workflow.md`; scoring tiếp tục bị
chặn cho đến khi intake thực tế vượt toàn bộ gate.

Ngày 2026-09-24, 30 SEC reserve candidate có độ khớp identity cao hơn được tạo
thêm và mười ứng viên đầu đã được thử capture. Chín raw HTML mới pass hash/schema;
cộng với hai capture chính, nhánh legitimate hiện có 11 artifact đã trích text.
Cả chín reserve record đều được first pass đề xuất `SAME_ENTITY_LIKELY`, nhưng
đây không phải nhãn: human-confirmed vẫn là 0 và eligible legitimate vẫn là 0.
Nhánh `CONFIRMED` chưa có observed solicitation artifact, nên external scoring
tiếp tục bị chặn.
