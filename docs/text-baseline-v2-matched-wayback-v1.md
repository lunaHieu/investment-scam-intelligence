# Text Baseline V2 – matched Wayback external benchmark V1

## Mục tiêu

Chấm đúng model `ISI_TEXT_BASELINE_V2` đã đóng băng trên benchmark external gồm 18 archived-homepage artifacts. Cả `CONFIRMED` và `LEGITIMATE` đều dùng stratum `WAYBACK_ARCHIVED_HOMEPAGE_HTML`, vì vậy kết quả ít bị confounding bởi cách capture hơn pilot 21 case trước.

Project owner đã mở riêng cổng **scoring** sau khi benchmark 9–9 và independent blinded AI second-review được báo cáo. Acceptance không cho phép training, tuning, đổi threshold, đổi vectorizer hoặc deployment. Benchmark gốc không bị sửa; acceptance được lưu thành artifact hash-bound riêng.

## Hợp đồng chấm

- Model artifact SHA-256: `c58444996e0ae67a9739c588e3d088f1f57eb1af7f9105e10a647303ce72fc71`.
- Feature input duy nhất: text đã extract từ archived homepage.
- Evidence của regulator/SEC/IAPD không đi vào feature matrix.
- Threshold giữ nguyên `0.5`.
- Fit operations: `0`.
- Các partition dùng khi model gốc được fit: `train + validation` của `group_split_v2`; `auxiliary + quarantine` không được dùng.

## Kết quả

- 18 record: 9 `CONFIRMED`, 9 `LEGITIMATE`.
- Accuracy: `0.666667`.
- Balanced accuracy: `0.666667`.
- Macro-F1: `0.6625`.
- ROC-AUC: `0.592593`.
- Average precision: `0.600812`.
- Confusion matrix: TN=`5`, FP=`4`, FN=`2`, TP=`7`.
- Recall `LEGITIMATE`: `0.555556`; recall `CONFIRMED`: `0.777778`.

So với pilot 21 case trước, Macro-F1 tăng từ `0.611111` lên `0.6625` và ROC-AUC tăng từ `0.545455` lên `0.592593`. Đây chỉ là mô tả giữa hai pilot nhỏ, không phải kiểm định cải thiện model: tập case và giao thức capture khác nhau, khoảng bất định rộng và không có model change.

## Giới hạn và quyết định

- Second review là AI độc lập được làm mù, không phải independent human review.
- Cùng cách capture không có nghĩa là đã loại bỏ mọi source effect; nguồn bằng chứng xác lập hai lớp vẫn khác nhau.
- Sáu lỗi trên 18 mẫu và ROC-AUC chỉ khoảng `0.593` cho thấy transfer còn yếu.
- Không dùng benchmark này để tune model hoặc chọn threshold. Nó phải được giữ làm external diagnostic đã mở một lần.
- Không có cơ sở cho deployment, enforcement, blocking hoặc diễn giải score như xác suất lừa đảo thực tế.

## Tệp kết quả

- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_baseline_v2\matched_wayback_v1\matched_wayback_results_v1.json`
- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_baseline_v2\matched_wayback_v1\matched_wayback_predictions_v1.jsonl`
- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_baseline_v2\matched_wayback_v1\matched_wayback_report_v1.md`

Verifier:

```powershell
.venv\Scripts\python.exe scripts\verify_text_baseline_v2_matched_wayback.py --registry registry\analyses\text_baseline_v2_matched_wayback_v1.json
```
