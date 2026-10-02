# Mendeley text challenger V2 – validation-only decision

## Câu hỏi nghiên cứu

Error analysis trên matched Wayback cho thấy một confirmed page tiếng Hà Lan chỉ phủ khoảng 7,1% word vocabulary. Protocol vì vậy cho phép đúng một replication đã khai báo trước: ghép word TF-IDF unigram/bigram với `char_wb` TF-IDF 3–5 gram trên `group_split_v2`.

Đây không phải tìm kiếm hyperparameter. Classifier, threshold, word branch và character branch đều được khóa trước khi chạy. Kết quả ablation `group_split_v1` trước đây là adverse evidence: word+char đã không được promote và còn tăng source predictability. Lần V2 chỉ kiểm tra xem kết luận có thay đổi sau khi loại auxiliary source và sửa split leakage hay không.

## Phạm vi dữ liệu

- Fit: 3.916 dòng `train`.
- Selection: 838 dòng `validation`.
- Internal test: không load text, không transform, không dùng label.
- Auxiliary và quarantine: không dùng.
- External Wayback benchmark: không load và không transform.
- Source name chỉ dùng cho stratified metrics và diagnostic source-predictability, không đi vào scam feature matrix.

## Kết quả validation

| Phép đo | Word baseline | Word + char_wb | Chênh lệch |
|---|---:|---:|---:|
| Pooled Macro-F1 | 0,700118 | 0,708630 | +0,008512 |
| Source-mean Macro-F1 | 0,778049 | 0,785748 | +0,007699 |
| Worst-source Macro-F1 | 0,480842 | 0,493497 | +0,012655 |
| Source predictability Macro-F1 | 0,907602 | 0,953110 | +0,045508 |
| Within-source shuffled-label Macro-F1 | 0,542893 | 0,544640 | +0,001747 |

Theo từng nguồn, challenger tăng `cresci_stock_2018` +0,023255, `spam_email` +0,007885 và `twitter_bot_detection` +0,012655, nhưng giảm `phishing` −0,013002.

Paired group bootstrap trên 808 validation groups:

- Macro-F1 delta: `+0,008512`.
- 95% percentile interval: `[-0,007058; 0,024308]`.
- Xác suất bootstrap challenger tốt hơn baseline: `0,858`.

## Quyết định

Challenger thất bại 3/7 promotion gates:

1. Source-mean gain `+0,007699`, thấp hơn mức tối thiểu `+0,01`.
2. Source predictability tăng `+0,045508`, vượt mức tối đa `+0,02`.
3. Bootstrap CI lower bound `−0,007058`, không đạt yêu cầu ≥ 0.

Do mọi gate đều bắt buộc, giữ `ISI_TEXT_BASELINE_V2` word-only. Không mở internal test, không tạo challenger model artifact và không chấm lại bất kỳ external benchmark nào.

Kết quả này củng cố kết luận của ablation V1: character features có thể tăng nhẹ điểm nội bộ nhưng đồng thời mã hóa source/style mạnh hơn. Chúng chưa chứng minh khả năng tổng quát đa ngôn ngữ.

## Bước tiếp theo hợp lệ

Không tiếp tục thử các biến thể character khác trên cùng validation partition. Ưu tiên mở rộng dữ liệu external mới có cả hai lớp trong từng language/capture stratum. Nếu sau này nghiên cứu multilingual representation, phải tạo protocol mới, sử dụng nested validation hoặc development split mới và giữ một external benchmark mới chưa mở.

## Tệp kết quả

- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_challenger_v2_validation\text_challenger_v2_validation_selection.json`
- `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_challenger_v2_validation\text_challenger_v2_validation_predictions.jsonl`

Verifier:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_text_challenger_v2.py --registry registry\models\mendeley_text_challenger_v2.json
```
