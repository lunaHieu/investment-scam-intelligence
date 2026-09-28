# External-text matched Wayback benchmark V1

## Mục tiêu

Benchmark này giảm confounding của external pilot đầu tiên bằng cách giữ cùng một kiểu artifact cho cả hai lớp: `WAYBACK_ARCHIVED_HOMEPAGE_HTML`. Homepage capture trực tiếp từ SEC/IAPD không được trộn vào stratum này.

Điều này cân bằng **cách capture**, nhưng không loại bỏ hoàn toàn khác biệt nguồn bằng chứng: `CONFIRMED` vẫn cần regulator warning, còn `LEGITIMATE` vẫn cần SEC/IAPD registration và identity alignment. Không được diễn giải benchmark như một thí nghiệm đã loại bỏ mọi source effect.

## Thu thập và screening

- Tái sử dụng 10 Wayback capture `CONFIRMED` đã pin hash và tái tạo được normalized text.
- Truy vấn Wayback cho 11 host `LEGITIMATE` cũ: 10 có snapshot, 10 tải thành công, 7 vượt tiêu chí đã khóa.
- Không hạ ngưỡng sau khi thấy kết quả. Ba capture bị loại do identity mismatch, quá ít text hoặc thiếu investment markers.
- Chọn thêm 15 SEC/IAPD reserve host chưa dùng: 13 có snapshot, 10 tải thành công, 9 vượt screening.
- AI primary review trên 9 reserve: 8 `LEGITIMATE/HIGH`, 1 `UNCERTAIN/MEDIUM`. Đây không phải human review và chưa tạo benchmark label.

Mọi download chỉ truy cập `archive.org` hoặc `web.archive.org`. Không mở live suspicious domain, không tự follow redirect ra ngoài Wayback và không ghi đè raw capture.

## Independent second review

Reviewer thứ hai nhận packet mù, không có:

- case ID gốc;
- mapping sang nhãn vòng một;
- rationale vòng một;
- model prediction hoặc score.

Reviewer chỉ thấy archived artifact và evidence metadata. Reviewer là một AI context độc lập, được ghi rõ `INDEPENDENT_BLINDED_AI_SECOND_REVIEW_NOT_HUMAN`; dự án không tuyên bố đã có second-review độc lập bởi con người.

Primary packet có 20 case. Reviewer trả về 9 `CONFIRMED/HIGH`, 7 `LEGITIMATE/HIGH`, 3 `LEGITIMATE/MEDIUM` và 1 `UNCERTAIN/HIGH`. Reserve packet có thêm 5 legitimate: 4 `HIGH`, 1 `MEDIUM`.

Case `Falcon International/Barox International` bị giữ `UNCERTAIN` vì packet không đủ warning text để giải thích identity mismatch. Bốn legitimate case confidence `MEDIUM` cũng bị loại khỏi benchmark; không hạ ngưỡng confidence để đạt kích thước mong muốn.

## Kết quả reconciliation

- First/second-review agreement `CONFIRMED/HIGH`: 9.
- First/second-review agreement `LEGITIMATE/HIGH`: 11.
- Materialize theo lớp nhỏ hơn để giữ cân bằng: 9 `CONFIRMED` + 9 `LEGITIMATE` = 18 record.
- Mọi record thuộc duy nhất stratum `WAYBACK_ARCHIVED_HOMEPAGE_HTML`.
- Hai legitimate agreement dư được giữ ngoài benchmark để tránh làm lệch lớp.

Benchmark hiện ở trạng thái `OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING`. Chưa chạy model, chưa tune threshold/vectorizer, chưa fit model, không mở training hay deployment.

## Tệp chính

- Benchmark: `D:\nckh 2026-2027\ISI_Data\curated\external_text_matched_wayback_v1\matched_wayback_external_benchmark_v1.json`
- Reconciliation report: `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v1\reconciliation_report_v1.json`
- Primary second review: `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v1\second_review_v1\independent_second_review_v1.json`
- Reserve second review: `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v1\second_review_reserve_v1\independent_second_review_reserve_v1.json`

Verifier:

```powershell
.venv\Scripts\python.exe scripts\verify_external_text_matched_wayback_benchmark.py --registry registry\pilots\external_text_matched_wayback_benchmark_v1.json
```
