# External-text Wayback language benchmark V2

## Kết quả

Đã đóng băng một benchmark external-text English gồm 38 record cân bằng: 19 `CONFIRMED` và 19 `LEGITIMATE`. Tất cả record dùng cùng capture stratum `WAYBACK_ARCHIVED_HOMEPAGE_HTML`, có AI primary review `HIGH` và independent blinded AI second review `HIGH` đồng thuận.

Benchmark chưa được phép scoring. Trạng thái hiện tại là `OWNER_ACCEPTANCE_REQUIRED_BEFORE_MODEL_SCORING`; không có fit, tuning, threshold selection, training hoặc deployment trong giai đoạn này.

## Thu thập và kiểm tra raw

- Candidate provenance bắt nguồn từ IOSCO I-SCAN warning index và SEC/IAPD registration index; provenance không tự động trở thành nhãn.
- Chỉ gọi `archive.org`/`web.archive.org`; không truy cập live candidate domains.
- File capture phải tồn tại và khớp SHA-256 trong acquisition report. File lỗi, quá nhỏ, thiếu sau capture hoặc bị endpoint protection chặn không được xử lý tiếp.
- Lượt top-up thứ hai có 32 snapshot được yêu cầu, 30 file hash-verified/readable; hai confirmed capture bị loại do HTML 114 byte và HTTP 403.

## Screening và primary review

Sau ba lượt capture, offline reviewability screening có 22 confirmed-candidate English và 31 legitimate-candidate English có văn bản reviewable. Automatic language chỉ dùng để routing; AI primary reviewer xác nhận ngôn ngữ từ visible text.

Primary review bao phủ 54 artifact: 20 `CONFIRMED/HIGH`, 31 `LEGITIMATE/HIGH`, 2 `UNCERTAIN/MEDIUM`, 1 `REJECT_CAPTURE/HIGH`; 53 English và 1 Spanish. Đây là AI review, không phải human review.

Ba case bị loại khỏi English second-review benchmark:

- `finscorpio.com`: archive là mẫu WordPress/kiến trúc chưa tùy biến, không bảo toàn hoạt động impersonation bị cảnh báo.
- `alphaiberia.com`: archive chủ yếu là trang tổng hợp tin crypto; quan hệ với warning dịch vụ không phép chưa giải quyết được.
- `myetherwallet.com`: archive mô tả ví self-custody và ghi không phải tư vấn đầu tư; quan hệ với warning dịch vụ không phép chưa giải quyết được.

Một Spanish confirmed case được giữ làm reserve; không mở non-English stratum vì không có legitimate counterpart đủ ngưỡng.

## Independent blinded second review

Packet English được chọn cân bằng 19+19. Reviewer ở ngữ cảnh AI tách biệt chỉ được đọc packet mù và không được đọc:

- private mapping;
- candidate/source case ID gốc;
- reference branch;
- primary-review decision hoặc rationale;
- model output, prediction hoặc score.

Reviewer trả về 38 quyết định `HIGH`: 19 `CONFIRMED`, 19 `LEGITIMATE`, không có disagreement. Dự án ghi rõ đây là independent blinded **AI** second review, không tuyên bố human second review.

## Model firewall

Nếu project owner sau này chấp nhận mở scoring, model chỉ được nhận `records[].artifact.visible_text`. Warning/registry evidence, reviewer rationale, candidate provenance và label metadata không được đưa vào model input. Benchmark không được dùng để training hoặc tuning.

## Tệp chính

- Benchmark: `D:\nckh 2026-2027\ISI_Data\curated\external_text_matched_wayback_v2\wayback_language_benchmark_v2.json`
- Reconciliation: `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\reconciliation_report_v2.json`
- Registry: `registry/pilots/external_text_wayback_language_benchmark_v2.json`

Kiểm tra toàn bộ hash và invariant:

```powershell
.venv\Scripts\python.exe scripts\verify_external_text_wayback_language_benchmark_v2.py --registry registry\pilots\external_text_wayback_language_benchmark_v2.json
```
