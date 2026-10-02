# Text Baseline V2 – Wayback language V2 error analysis

## Phạm vi

Phân tích tái tạo toàn bộ 38 prediction và giải thích 13 lỗi bằng chính frozen vectorizer, coefficient, intercept và threshold `0.5`. Không fit/refit model, không đổi threshold, không relabel và không dùng internal test.

Train+validation cũ chỉ được transform để tìm hàng gần nhất trong không gian TF-IDF. Nearest neighbor và feature contribution là công cụ giải thích hành vi model, không phải bằng chứng gian lận hoặc quan hệ nhân quả.

## Kết quả chính

- 25/38 đúng; 9 false positive và 4 false negative.
- Model dự đoán label 1 cho 24/38 mẫu.
- 8/13 lỗi cách threshold không quá `0.10`.
- Tổng cộng 17/38 case nằm trong ±`0.10` quanh threshold, gồm 9 case đúng và 8 case sai.
- Brier score `0.210547`; ECE mô tả `0.121797`. Đây không phải calibration của xác suất scam ngoài thực tế.
- Cả 38 mẫu đều là English và cùng `WAYBACK_ARCHIVED_HOMEPAGE_HTML`.

## Domain shift

Nearest-fit similarity thấp trên toàn corpus. Trong 38 case, 31 có nearest fit từ `spam_email`, 4 từ `cresci_stock_2018`, 3 từ `phishing`; không case nào gần nhất với `twitter_bot_detection`. Trong 13 lỗi, 9 case gần nhất với `spam_email`.

Điều này cho thấy frozen baseline vẫn phụ thuộc mạnh vào style/source của corpus Mendeley. Matching language và capture mode đã loại bớt hai confounder quan trọng nhưng chưa làm external webpages giống dữ liệu fit.

## Chín false positive

Các trang advisory/investment đã review là legitimate bị đẩy về label 1 bởi những feature lặp lại:

- `your` xuất hiện trong top contribution của 9/9 false positive;
- `our` trong 9/9;
- `you` trong 7/9;
- tiếp theo là `why`, `home`, `account`, `service`, `banking`, `investing`.

Đây chủ yếu là ngôn ngữ marketing, điều hướng và giao tiếp trực tiếp bình thường trên website tài chính. Model đã học shortcut từ phishing/spam nên không thể coi riêng các từ này là scam indicators.

False-positive score có median `0.596374`; phần lớn nằm tương đối gần threshold. Tuy nhiên threshold không được điều chỉnh từ benchmark đã mở.

## Bốn false negative

Các feature kéo confirmed pages về label 0 lặp lại là `markets`, `trade`, `management`, `options`, `investor`, `real estate`, cùng các từ chức năng `in`, `for`, `about`.

Điển hình:

- `blueq.org` và `esperio.org` bị các từ trading/markets/options kéo xuống;
- `wpfinvestment.com` bị `land`, `investor`, `estate`, `management` kéo về label 0;
- `ibointernational.com` gần threshold, với tín hiệu `markets/global` đối nghịch `account/security/your`.

False-negative vocabulary coverage trung bình `0.487283`, không còn tình trạng OOV cực đoan như case non-English ở benchmark V1. Vấn đề còn lại chủ yếu là ngữ nghĩa tài chính hợp pháp và cảnh báo cùng chia sẻ vocabulary.

## Kết luận phương pháp

Không đổi threshold từ 17 case gần ranh giới. Việc làm đó sẽ biến external benchmark thành tập tuning.

Các giả thuyết có thể ghi nhận cho một protocol tương lai gồm representation bớt nhạy với source/style, giảm trọng số shortcut marketing chung, và bổ sung tín hiệu cấu trúc không rò rỉ evidence label. Mọi challenger phải được khai báo trước, phát triển/chọn bằng train+validation phù hợp và đánh giá trên external data mới chưa mở.

## Tệp kết quả

- `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\text_baseline_v2_error_analysis\wayback_language_error_analysis_v2.json`
- `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\text_baseline_v2_error_analysis\wayback_language_diagnostics_v2.jsonl`
- `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\text_baseline_v2_error_analysis\wayback_language_error_queue_v2.jsonl`
- `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\text_baseline_v2_error_analysis\wayback_language_near_threshold_queue_v2.jsonl`

Verifier sau khi registry được tạo:

```powershell
.venv\Scripts\python.exe scripts\verify_text_baseline_v2_wayback_language_v2_error_analysis.py --registry registry\analyses\text_baseline_v2_wayback_language_v2_error_analysis.json
```
