# Mendeley text challenger V3 – English stop-word style guard

## Câu hỏi nghiên cứu

Error analysis trên benchmark Wayback language V2 cho thấy các từ chỉ phong cách giao tiếp chung như `your`, `our`, `you`, `in`, `for` và `about` xuất hiện lặp lại trong contribution của các lỗi. V3 kiểm tra đúng một giả thuyết đã khóa trước: dùng danh sách English stop words chuẩn của scikit-learn trong word TF-IDF, giữ nguyên toàn bộ Logistic Regression, ngưỡng và các tham số TF-IDF khác.

Không có danh sách từ chỉnh tay. Benchmark Wayback đã mở chỉ tạo giả thuyết và không được load, transform hoặc chấm lại trong V3.

## Thiết kế chống tuning lặp lại

- Development chính: bốn fold out-of-fold theo `split_group_id` bên trong 3.916 dòng train.
- Mỗi group nằm trọn trong một fold; assignment được cân theo từng `source_dataset × label` bằng thứ tự SHA-256 cố định.
- Confirmation: sau khi đã có đủ prediction OOF, cả baseline và challenger được fit trên toàn bộ train rồi chấm đúng một lần trên 838 dòng validation cũ.
- Internal test, auxiliary, quarantine và mọi external benchmark đều bị khóa.
- Chỉ một challenger, không tìm kiếm hyperparameter và không đổi threshold `0.5`.

## Kết quả development OOF

| Phép đo | Word baseline | Bỏ English stop words | Chênh lệch |
| --- | ---: | ---: | ---: |
| Pooled Macro-F1 | 0,708102 | 0,714952 | +0,006850 |
| Source-mean Macro-F1 | 0,785928 | 0,793511 | +0,007583 |
| Worst-source Macro-F1 | 0,493596 | 0,500890 | +0,007294 |
| Source predictability Macro-F1 | 0,917801 | 0,913441 | −0,004360 |
| Within-source shuffled-label Macro-F1 | 0,558920 | 0,573777 | +0,014857 |

Development cải thiện ba metric dự đoán chính và giảm nhẹ khả năng nhận diện nguồn. Tuy nhiên shuffled-label diagnostic tăng `0,014857`, vượt trần `0,01`, nên development đã không qua toàn bộ gate. Điều này cảnh báo rằng representation vẫn có thể khai thác liên hệ nhãn–nguồn dù đã bỏ stop words.

## Kết quả validation confirmation

| Phép đo | Word baseline | Bỏ English stop words | Chênh lệch |
| --- | ---: | ---: | ---: |
| Pooled Macro-F1 | 0,700118 | 0,677621 | −0,022497 |
| Source-mean Macro-F1 | 0,778049 | 0,764394 | −0,013655 |
| Worst-source Macro-F1 | 0,480842 | 0,435593 | −0,045249 |
| Source predictability Macro-F1 | 0,907602 | 0,913614 | +0,006012 |

Theo nguồn, challenger thay đổi:

- `cresci_stock_2018`: −0,018154 Macro-F1;
- `phishing`: −0,014531;
- `spam_email`: +0,023314;
- `twitter_bot_detection`: −0,045249.

Paired group bootstrap trên 808 validation groups cho delta Macro-F1 `−0,022498`, khoảng percentile 95% `[−0,042531; −0,003272]`, xác suất challenger tốt hơn baseline `0,012`. Khoảng này hoàn toàn dưới 0.

## Quyết định

Loại `word_1_2_english_stopwords` và giữ `ISI_TEXT_BASELINE_V2`. Candidate thất bại 1/6 development gates và toàn bộ 6/6 validation confirmation gates.

Việc bỏ stop words giúp nhẹ trong cross-validation nội bộ nhưng không ổn định khi chuyển sang validation đã khóa. Nó còn làm representation nhận diện nguồn tốt hơn trên validation, trái với mục tiêu style guard. Không mở internal test, không tạo model artifact, không chấm lại Wayback và không deployment.

Không thử thêm biến thể stop-word hoặc danh sách từ thủ công trên cùng validation. Bước model tiếp theo chỉ hợp lệ khi có một hypothesis khác về bản chất và một evaluation mới chưa mở; trước mắt nên ưu tiên thu thập thêm external benchmark mới có cả hai lớp trong cùng capture/language stratum.

## Artifact

- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_challenger_v3_validation\text_challenger_v3_validation_selection.json`
- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_challenger_v3_validation\text_challenger_v3_development_oof_predictions.jsonl`
- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_challenger_v3_validation\text_challenger_v3_validation_predictions.jsonl`

Verifier sau khi registry được tạo:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_text_challenger_v3.py --registry registry\models\mendeley_text_challenger_v3.json
```
