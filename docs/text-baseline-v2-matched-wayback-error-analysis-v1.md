# Text Baseline V2 – matched Wayback error analysis V1

## Phạm vi

Phân tích tái tạo toàn bộ 18 prediction của benchmark Wayback 9–9 và giải thích sáu lỗi bằng chính vectorizer, coefficient và threshold đã đóng băng. Không fit/refit model, không đổi threshold, không relabel và không dùng internal test.

Train+validation cũ chỉ được transform để tìm hàng gần nhất trong không gian TF-IDF. Nearest neighbor và feature contribution là công cụ giải thích hành vi model, không phải bằng chứng gian lận hay quan hệ nhân quả.

## Kết quả chính

- 12/18 đúng; 4 false positive và 2 false negative.
- Model dự đoán label 1 cho 11/18 mẫu.
- 3/6 lỗi cách threshold `0.5` không quá `0.10`.
- Cả 18 mẫu cùng stratum `WAYBACK_ARCHIVED_HOMEPAGE_HTML`; capture-mode confounding đã giảm so với pilot cũ.
- Nearest-fit similarity của các lỗi rất thấp, trung bình khoảng `0.154`, cho thấy external homepage text khác rõ so với dữ liệu fit.
- 14/18 nearest fit đến từ `spam_email`; trong sáu lỗi có bốn nearest fit từ nguồn này. Đây là dấu hiệu baseline còn phụ thuộc style của nguồn huấn luyện.

## Bốn false positive

Bốn website tư vấn/tài chính hợp pháp bị dự đoán label 1 với score từ `0.5513` đến `0.6754`. Những feature đẩy score lên xuất hiện lặp lại là:

- `your`, `you`, `our`;
- `only`, `provide`, `why`;
- `money`, `investing`, `banking`, `account`.

Nhiều từ là ngôn ngữ marketing hoặc giao tiếp trực tiếp bình thường trên website tài chính. Model đã học liên hệ thống kê từ corpus hỗn hợp—đặc biệt phishing/spam—nên chúng không thể được coi là scam indicators độc lập.

## Hai false negative

- `MWB1_015`: trang tiếng Hà Lan, score `0.4827`. Chỉ `68/958` unique analyzed terms khớp vocabulary, coverage khoảng `0.071`. Đây là thất bại domain/language coverage rõ rệt.
- `MWB1_016`: trang prop-trading, score `0.4185`. Các từ `markets`, `trade`, `capital`, `prop`, `investor` kéo logit về label 0 dù các từ `account`, `your`, `money`, `trading` đẩy ngược lại.

Hai lỗi cho thấy mô hình word-level tiếng Anh không ổn định trước ngôn ngữ khác và có thể coi từ vựng trading thông thường là tín hiệu hợp pháp dù ngữ cảnh tổng thể cần cảnh báo.

## Kết luận phương pháp

Không đổi threshold từ sáu lỗi này. Dù ba lỗi gần threshold, chọn threshold mới trên benchmark đã mở sẽ biến external evaluation thành tập tuning và làm mất giá trị đánh giá độc lập.

Nếu phát triển challenger sau này, giả thuyết phải được khai báo trước, ví dụ:

- representation chịu được đa ngôn ngữ/OOV tốt hơn;
- giảm shortcut theo source/style;
- kết hợp các nhóm tín hiệu có provenance rõ ràng nhưng không đưa nhãn/evidence trực tiếp vào feature matrix.

Challenger phải được chọn bằng train/validation hoặc nested validation và đánh giá trên dữ liệu external mới chưa mở. Benchmark Wayback V1 này chỉ còn vai trò diagnostic, không được dùng lại để chọn cấu hình.

## Tệp kết quả

- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_baseline_v2\matched_wayback_error_analysis_v1\matched_wayback_error_analysis_v1.json`
- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_baseline_v2\matched_wayback_error_analysis_v1\matched_wayback_diagnostics_v1.jsonl`
- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_baseline_v2\matched_wayback_error_analysis_v1\matched_wayback_error_queue_v1.jsonl`

Verifier:

```powershell
.venv\Scripts\python.exe scripts\verify_text_baseline_v2_matched_wayback_error_analysis.py --registry registry\analyses\text_baseline_v2_matched_wayback_error_analysis_v1.json
```
