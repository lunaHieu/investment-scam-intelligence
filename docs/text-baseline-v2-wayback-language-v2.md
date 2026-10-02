# Text Baseline V2 – Wayback language benchmark V2

## Phạm vi

Project owner đã chấp nhận mở riêng frozen scoring sau khi benchmark English 19–19 được hash-pin và independent blinded AI second review hoàn tất. Acceptance không mở training, tuning, thay threshold/vectorizer, refit hoặc deployment.

Model `ISI_TEXT_BASELINE_V2` được giữ nguyên với threshold `0.5`. Feature matrix chỉ nhận `artifact.visible_text`; warning/registration evidence, provenance, nhãn và review rationale không được đưa vào model.

## Kết quả

Trên 38 mẫu:

- Accuracy: `0.657895`
- Balanced accuracy: `0.657895`
- Macro-F1: `0.651868`
- ROC-AUC: `0.739612`
- Average precision: `0.784833`
- Confusion: `TN=10, FP=9, FN=4, TP=15`

Model nhận đúng 25/38 mẫu và sai 13. Recall của `CONFIRMED` là `0.789474`, trong khi recall của `LEGITIMATE` là `0.526316`; lỗi hiện nghiêng về việc đẩy legitimate advisory/investment pages sang label 1.

## Diễn giải

Kết quả cho thấy word TF-IDF baseline có khả năng xếp hạng nhất định trên corpus mới (`ROC-AUC 0.739612`) nhưng quyết định ở threshold đóng băng vẫn chưa đủ ổn định (`Macro-F1 0.651868`). Benchmark lớn hơn V1 nhưng vẫn nhỏ và được lấy từ hai nguồn evidence khác nhau; không được diễn giải score như xác suất scam hoặc bằng chứng sẵn sàng deployment.

Kết quả này không được dùng để sửa threshold hoặc chọn model. Bước kế tiếp theo workflow là error analysis chẩn đoán trên 13 lỗi và các case sát threshold, giữ nguyên model firewall. Bất kỳ challenger nào sau này phải được khai báo trước và chọn chỉ bằng train/validation phù hợp, không tune trên external benchmark này.

## Tệp chính

- Results: `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\text_baseline_v2_evaluation\wayback_language_results_v2.json`
- Predictions: `D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\text_baseline_v2_evaluation\wayback_language_predictions_v2.jsonl`
- Acceptance: `configs/external_text_wayback_language_owner_acceptance_v2.json`

Verifier sau khi registry được tạo:

```powershell
.venv\Scripts\python.exe scripts\verify_text_baseline_v2_wayback_language_v2.py --registry registry\analyses\text_baseline_v2_wayback_language_v2.json
```
