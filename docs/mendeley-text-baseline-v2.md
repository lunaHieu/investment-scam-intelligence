# Text baseline V2 trên Mendeley group split V2

## Kết luận

`ISI_TEXT_BASELINE_V2` là baseline text nội bộ mới dùng strict `group_split_v2`. Model chỉ nhận `text_content`; không dùng `source_dataset`, metadata, `split_group_id`, auxiliary hoặc quarantine làm feature.

Baseline được giữ để làm mốc tái lập, **không được triển khai**. Test Macro-F1 là 0,7062 và hiệu năng khác nhau rất mạnh giữa các nguồn. Riêng `twitter_bot_detection` có Macro-F1 0,4761 và ROC-AUC 0,4564, nên model chưa thể hiện khả năng tổng quát ổn định.

## Giao thức chống dùng test để chọn model

Workflow được tách thành hai chương trình và hai thời điểm:

1. `select_mendeley_text_baseline_v2.py` chỉ giữ text/label của train và validation. Nó scan partition/routing của toàn CSV nhưng không giữ, transform hoặc tính metric trên test, auxiliary và quarantine.
2. Selection được ghi thành `validation_selection_v2.json`, sau đó verifier kiểm tra status, candidate grid, winner, SHA-256 và selection digest.
3. Chỉ sau khi selection hợp lệ, `evaluate_mendeley_text_baseline_v2.py` mới đọc test. Model cuối được refit trên train+validation bằng cấu hình đã khóa, rồi test được dùng một lần để báo cáo.

Selection được đóng băng lúc `2026-09-16T00:05:00+00:00`; test evaluation bắt đầu ở artifact lúc `2026-09-16T00:10:00+00:00`.

## Dữ liệu được dùng

| Vai trò | Số dòng | Cách sử dụng |
| --- | ---: | --- |
| Train | 3.916 | Fit vectorizer và 10 candidate trong pha selection. |
| Validation | 838 | Chọn candidate; sau khi khóa selection được nhập vào final refit. |
| Test | 838 | Không dùng trong selection; chỉ báo cáo cuối. |
| Auxiliary | 10.607 | Không load vào feature/model. |
| Quarantine | 3 | Không load vào feature/model. |

Final fit dùng 4.754 dòng train+validation. Split SHA-256 được pin ở `98f75387a4a598d85a6f721d10808979bda694dad8f85354d595679bdd96e734`.

## Feature và candidate

Vectorizer được cố định trước selection:

- word TF-IDF unigram + bigram;
- lowercase, Unicode accent stripping;
- `min_df=2`, `max_df=0.995`, tối đa 100.000 feature;
- sublinear term frequency.

Logistic Regression dùng `liblinear`, threshold 0,5 và random state `20260916`. Candidate grid gồm `C = 0.25, 0.5, 1, 2, 4` kết hợp với `class_weight = None` hoặc `balanced`.

Tiêu chí chọn theo thứ tự:

1. Trung bình không trọng số của validation Macro-F1 theo từng nguồn.
2. Worst-source validation Macro-F1.
3. Pooled validation Macro-F1.
4. Pooled validation balanced accuracy.
5. Candidate xuất hiện sớm hơn trong grid đã khai báo.

Candidate thắng là `C=2.0`, `class_weight=None`.

| Candidate | Source-mean Macro-F1 | Worst-source Macro-F1 | Pooled Macro-F1 |
| --- | ---: | ---: | ---: |
| `C=1.0`, none | 0,7543 | 0,4809 | 0,6829 |
| **`C=2.0`, none** | **0,7780** | 0,4808 | **0,7001** |
| `C=4.0`, none | 0,7694 | 0,4706 | 0,6919 |
| `C=2.0`, balanced | 0,7765 | 0,4806 | 0,6991 |
| `C=4.0`, balanced | 0,7739 | 0,4804 | 0,6980 |

Bảng chỉ hiển thị các candidate gần quyết định; selection artifact giữ đủ cả 10 cấu hình.

## Kết quả validation đã dùng để chọn

| Metric | Giá trị |
| --- | ---: |
| Accuracy | 0,7005 |
| Macro-F1 | 0,7001 |
| Balanced accuracy | 0,7001 |
| ROC-AUC | 0,7975 |
| Average precision | 0,7960 |
| Trung bình Macro-F1 theo nguồn | 0,7780 |
| Worst-source Macro-F1 | 0,4808 (`twitter_bot_detection`) |

Selection có SHA-256 `a506fde7a22ff2a27a9d97506a28c95bd714aa80438e2a30c9ecb5947783092b` và digest `fcb455d05264411e2f97e13eea53bd3d2c75c8f0809bb1d1d71ecb7c457b684b`.

## Kết quả internal test sau khi khóa selection

| Metric | Giá trị |
| --- | ---: |
| Accuracy | 0,7064 |
| Macro-F1 | 0,7062 |
| Balanced accuracy | 0,7062 |
| ROC-AUC | 0,8109 |
| Average precision | 0,8125 |
| F1 label 0 | 0,7146 |
| F1 label 1 | 0,6978 |

Confusion matrix: TN 308, FP 118, FN 128, TP 284.

### Theo nguồn

| Nguồn | Dòng test | Macro-F1 | Balanced accuracy | ROC-AUC |
| --- | ---: | ---: | ---: | ---: |
| `cresci_stock_2018` | 116 | 0,8362 | 0,8396 | 0,8949 |
| `phishing` | 158 | 0,9007 | 0,9181 | 0,9804 |
| `spam_email` | 166 | 0,9691 | 0,9625 | 0,9936 |
| `twitter_bot_detection` | 398 | 0,4761 | 0,4764 | 0,4564 |

Trung bình không trọng số Macro-F1 theo nguồn là 0,7955, cao hơn pooled Macro-F1 vì ba nguồn nhỏ có kết quả tốt, trong khi nguồn Twitter lớn hơn và gần mức ngẫu nhiên kéo mạnh metric pooled xuống. Vì vậy không được chỉ báo cáo source-mean mà bỏ pooled result hoặc worst-source.

## Cách diễn giải

- Đây là model học nhãn benchmark của Mendeley, không phải xác suất lừa đảo đầu tư trong thực tế.
- Hệ số TF-IDF có thể phản ánh phong cách và dấu vết nguồn; không phải bằng chứng nhân quả về fraud.
- Không so trực tiếp số V2 với V1 như một cải thiện model: V2 loại toàn bộ nguồn `fake_profile_post`, quarantine nhãn mâu thuẫn và có cấu trúc split khác.
- Zero known-template crossing không chứng minh không còn semantic near-duplicate; audit V2 vẫn có các cặp cosine cao.
- Test V2 đã mở và từ đây chỉ được dùng để báo cáo cố định. Không được đổi vectorizer, threshold, feature hay hyperparameter theo kết quả test.

## Artifact và kiểm tra

Artifact nằm tại:

```text
D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\text_baseline_v2\
```

Gồm selection, model `joblib`, results và 838 test predictions. Registry đóng băng nằm tại `registry/models/text_baseline_v2.json`.

Kiểm tra toàn bộ hash, selection ordering, model metadata, prediction coverage và tái tính metrics:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_text_baseline_v2_registry.py
```

## Bước tiếp theo

Giữ nguyên model V2. Có thể thực hiện error analysis trên test để hiểu failure mode nhưng không được dùng kết quả đó để chỉnh model rồi báo lại trên cùng test. Gate đánh giá tiếp theo phải là curated cases có evidence độc lập hoặc một external dataset chưa dùng cho lựa chọn.
