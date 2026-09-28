# Quy trình intake external text có evidence

## Mục đích

Quy trình này chuẩn bị dữ liệu external để đánh giá nguyên cấu hình
`ISI_TEXT_BASELINE_V2`. Nó không tự mở URL nghi vấn, không tự tạo nhãn, không
fit lại model và không báo metric khi chưa đủ tối thiểu 10 `CONFIRMED` và 10
`LEGITIMATE`.

Template trống nằm tại:
`registry/pilots/external_text_evaluation_intake_template.json`.

Validator nằm tại:
`scripts/validate_external_text_intake.py`.

## Một record hợp lệ là gì

Một record phải là chính nội dung mà model dự kiến phân loại:

- `POST`: bài đăng hoặc quảng cáo đầu tư quan sát được.
- `MESSAGE`: tin nhắn hoặc lời mời đầu tư quan sát được.
- `WEBSITE_SNAPSHOT`: nội dung trang đầu tư đã được lưu thành capture.

Không dùng complaint, warning document hoặc bài báo mô tả vụ việc làm input
text. Các tài liệu đó chỉ được đưa vào `evidence`.

Mỗi record phải có:

1. Text quan sát được với tối thiểu 20 ký tự không phải khoảng trắng.
2. File capture gốc lưu dưới raw root và SHA-256 khớp.
3. URL nguồn và source record ID nếu nguồn cung cấp.
4. `case_or_campaign_group_id` để các artifact cùng vụ không bị coi là độc lập.
5. `near_duplicate_group_id` để gom các bản sao hoặc template gần nhau.
6. Evidence đã review hỗ trợ đúng kết luận.
7. `label_confidence: HIGH` và `review_status: RECONCILED` trước khi đủ điều kiện.

## CONFIRMED và LEGITIMATE

`CONFIRMED` cần evidence đã review hỗ trợ `SCAM_CLAIM`. Ít nhất một evidence
phải là enforcement record, court record, regulator warning hoặc cross-check
độc lập. Một complaint đơn lẻ không đủ.

`LEGITIMATE` cần evidence đã review hỗ trợ `LEGITIMACY`, như official registry,
court/enforcement record hoặc cross-check độc lập. Không thấy một entity trong
danh sách cảnh báo không phải bằng chứng hợp pháp. Đăng ký của một entity cũng
không tự động chứng minh mọi URL mang tên entity đó là an toàn; identity của
artifact và entity phải khớp.

## Việc người nghiên cứu phải làm

1. Truy cập nguồn bằng cách hợp lệ trong trình duyệt hoặc qua export chính thức.
2. Lưu file gốc, HTML, PDF, JSON/CSV export hoặc ảnh chụp vào raw root.
3. Xác nhận capture thực sự chứa artifact cần đánh giá.
4. Xem evidence mâu thuẫn và quyết định `CONFIRMED`, `LEGITIMATE` hoặc
   `UNCERTAIN`.
5. Chỉ đặt `RECONCILED` sau khi đã giải quyết mâu thuẫn và kiểm tra identity.

AI có thể làm phần còn lại sau khi nhận đường dẫn file: tính hash, trích text,
tạo draft JSON, kiểm tra ID/group, phát hiện evidence thiếu, kiểm tra duplicate
và chạy readiness gate. AI không tự nâng case thành `CONFIRMED` hoặc
`LEGITIMATE`.

## Vị trí lưu raw đề xuất

```text
D:\nckh 2026-2027\ISI_Data\raw\
  dfpi_crypto_scam_tracker\YYYY-MM-DD\...
  sec_iapd\YYYY-MM-DD\...
  iosco_i_scan\YYYY-MM-DD\...
  ubcknn_warnings\YYYY-MM-DD\...
  external_text_captures\YYYY-MM-DD\...
```

Trong intake JSON, `source_capture_path` phải là đường dẫn tương đối so với raw
root, ví dụ:

`external_text_captures/2026-09-23/case-001.html`

Validator từ chối đường dẫn tuyệt đối, `..`, file không tồn tại hoặc hash sai.

## Cấu trúc record mẫu

Đoạn dưới chỉ minh họa field; không phải dữ liệu thật và không được đưa vào
evaluation:

```json
{
  "case_id": "CASE_REPLACE_ME",
  "ground_truth_status": "UNCERTAIN",
  "label_confidence": "LOW",
  "review_status": "UNREVIEWED",
  "review_rationale": "Replace after human evidence review.",
  "case_or_campaign_group_id": "CASEGRP_REPLACE_ME",
  "near_duplicate_group_id": "NDG_REPLACE_ME",
  "artifact": {
    "artifact_id": "ART_REPLACE_ME",
    "source_id": "external_text_captures",
    "source_record_id": null,
    "artifact_type": "WEBSITE_SNAPSHOT",
    "text": "Replace with exact observed text.",
    "text_sha256": "replace_with_sha256_of_exact_utf8_text",
    "language": "en",
    "url": "https://source.example/replace-me",
    "collection_date": "YYYY-MM-DD",
    "content_observed_at": "YYYY-MM-DDTHH:MM:SS+00:00",
    "source_capture_path": "external_text_captures/YYYY-MM-DD/replace-me.html",
    "source_capture_sha256": "replace_with_capture_file_sha256"
  },
  "evidence": [
    {
      "evidence_id": "EVD_REPLACE_ME",
      "evidence_type": "regulator_warning",
      "source_id": "replace_source",
      "source_url": "https://official.example/replace-me",
      "summary": "Neutral summary of what the evidence supports.",
      "supports": [],
      "reviewed": false
    }
  ]
}
```

## Chạy validator

Kiểm tra draft nhưng chưa bắt buộc đủ 20 record:

```powershell
.venv\Scripts\python.exe scripts\validate_external_text_intake.py `
  --input <intake.json> `
  --raw-root "D:\nckh 2026-2027\ISI_Data\raw" `
  --report <validation-report.json>
```

Khi chuẩn bị đánh giá model, thêm `--require-reporting-gate`. Lệnh sẽ thất bại
nếu chưa đủ toàn bộ điều kiện và số lượng:

```powershell
.venv\Scripts\python.exe scripts\validate_external_text_intake.py `
  --input <intake.json> `
  --raw-root "D:\nckh 2026-2027\ISI_Data\raw" `
  --require-reporting-gate
```

Chỉ sau khi gate này pass mới được xây dựng external evaluation artifact cho
model đóng băng. Gate pass vẫn chỉ cho phép báo cáo pilot nhỏ, không cho phép
deployment hoặc tuyên bố hiệu năng tổng quát.

## Trạng thái hiện tại

Trạng thái mới nhất ngày 2026-09-24:

- DFPI raw: 0 file.
- SEC IAPD: 1 raw feed đã tải, xác minh và khóa SHA-256; chỉ dùng làm
  entity/registration reference.
- IOSCO I-SCAN: 1 CSV export gồm 47.001 record đã tải, xác minh và khóa SHA-256;
  chỉ dùng làm warning evidence.
- UBCKNN raw captures: 0 file.
- Hàng đợi chính: 30 ứng viên đã lọc (`15 CONFIRMED_CANDIDATE` +
  `15 LEGITIMATE_CANDIDATE`). Reserve gồm 30 SEC candidate, 40 IOSCO candidate
  V1 và 100 IOSCO candidate V2; các host reserve không trùng queue trước.
  Candidate không phải label.
- Raw external HTML capture: 11 file từ host được SEC/IAPD ghi nhận và 22 raw
  replay từ Internet Archive. Có thêm 12 local capture của trang warning chính
  thức, chỉ dùng làm evidence.
- Draft intake: 11 legitimate và 10 confirmed artefact đã trích text, có
  manifest và pass structural/hash validation. Cả 21 vẫn
  `UNCERTAIN + LOW + IN_REVIEW`.
- AI-assisted first pass: 11 đề xuất `LEGITIMATE` và 10 đề xuất `CONFIRMED` để
  human review; human confirmation và label được tạo đều bằng 0.
- External text đủ điều kiện: 0 record.

Vì vậy external scoring vẫn bị chặn. Bước tiếp theo là human contradiction,
identity và evidence reconciliation cho 11 legitimate capture và 10 confirmed
capture. Bảy confirmed case chưa có local warning capture và một MoneySmart
capture chỉ có app shell đã được note để kiểm tra thủ công sau. Không cần truy
vấn 60 ứng viên IOSCO reserve V2 còn lại trước khi hoàn tất review hiện tại.
