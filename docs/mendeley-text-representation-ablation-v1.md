# Mendeley Text-Representation Ablation V1

## Kết luận

Giữ nguyên `ISI_TEXT_BASELINE_V1` dùng word TF-IDF. `word + char_wb` được chọn trước khi mở test nhờ validation source-mean Macro-F1 cao hơn baseline 0,59 điểm phần trăm, nhưng không đạt ngưỡng cải thiện 1 điểm đã đặt trước. Trên internal test, nó giảm Macro-F1 từ 87,26% xuống 87,12%, không cải thiện nguồn nào trong năm nguồn và khoảng tin cậy bootstrap theo nhóm chứa 0. Vì vậy không promote.

Kết quả character còn cho thấy dataset mang dấu vân tay nguồn và template rất mạnh. Đây là benchmark nhãn deceptive/suspicious đã harmonize từ Mendeley, không phải ground truth lừa đảo đầu tư đã được cơ quan có thẩm quyền xác minh.

## Câu hỏi thí nghiệm

Phép thử hỏi việc thay biểu diễn word unigram/bigram bằng character n-gram hoặc ghép word với character có cải thiện khả năng tổng quát hay không. Để chỉ đo tác động của representation, mọi biến thể dùng cùng Logistic Regression:

- `C=2`, `class_weight=None`, solver `liblinear`, threshold 0,5;
- vocabulary và IDF chỉ fit trên train;
- không tune lại hyperparameter hoặc threshold;
- `source_dataset`, `record_id`, partition, metadata và nhãn không nằm trong feature matrix.

Bốn representation được xem trên validation:

1. `word_1_2`: baseline word unigram/bigram.
2. `char_wb_3_5`: character 3–5 gram bên trong ranh giới từ.
3. `char_3_5`: raw character 3–5 gram, chỉ là stress-test source shortcut.
4. `word_1_2_plus_char_wb_3_5`: ghép sparse word và `char_wb`, sau đó L2-normalize.

`char_3_5` được khai báo trước là diagnostic-only nên không thể được promote và không được mở trên test. Representation hợp lệ được chọn bằng trung bình không trọng số Macro-F1 của năm nguồn trên validation; tie-break lần lượt bằng nguồn kém nhất, pooled Macro-F1 và representation đơn giản hơn. Sau khi khóa lựa chọn, chỉ baseline và challenger thắng được mở trên test.

## Kết quả validation

| Representation | Feature | Train nonzero | Pooled Macro-F1 | Source-mean Macro-F1 | Worst-source Macro-F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `word_1_2` | 63.745 | 721.819 | 87,65% | 83,61% | 50,40% |
| `char_wb_3_5` | 65.510 | 4.022.375 | 72,17% | 77,66% | 50,52% |
| `char_3_5` diagnostic | 100.000 | 6.563.427 | 88,71% | **84,78%** | **55,04%** |
| `word_1_2_plus_char_wb_3_5` | 129.255 | 4.744.194 | 87,42% | **84,20%** | 47,25% |

Trong nhóm được phép chọn, `word + char_wb` có source-mean cao nhất nên được khóa làm challenger. Tuy nhiên, mức tăng chỉ 0,59 điểm phần trăm, pooled Macro-F1 thấp hơn và worst-source giảm 3,15 điểm phần trăm.

Raw `char` có validation tốt nhất nhưng đã chạm trần 100.000 feature và rất dễ học emoji, dấu câu, placeholder, độ dài email và lỗi encoding đặc trưng cho từng nguồn. Việc không mở test cho biến thể này tránh chọn lại thiết kế sau khi nhìn test.

## Kiểm tra source shortcut

Một classifier chẩn đoán riêng được huấn luyện để dự đoán `source_dataset` từ từng representation. Source chỉ là nhãn của diagnostic này, không phải feature của model scam.

| Representation | Validation source-prediction Macro-F1 | Validation scam Macro-F1 sau khi shuffle nhãn trong từng nguồn |
| --- | ---: | ---: |
| `word_1_2` | 81,56% | 52,77% |
| `char_wb_3_5` | 88,24% | 52,59% |
| `char_3_5` | 88,35% | 53,33% |
| `word_1_2_plus_char_wb_3_5` | 88,04% | 52,25% |

Character representation nhận diện nguồn rất mạnh. Khi phá liên hệ text–label bên trong từng nguồn nhưng giữ tỷ lệ nhãn theo nguồn, Macro-F1 vẫn khoảng 52–53%. Điều này xác nhận một phần tín hiệu dự báo có thể đến từ source identity và source-specific label prevalence, không chỉ từ nội dung lừa đảo.

## Kiểm tra template và near-duplicate

Split hiện tại không có `split_group_id` hoặc exact text vượt partition. Tuy nhiên, một audit chẩn đoán mới dùng NFKC, lowercase, thay URL/email/handle/placeholder, thay mỗi chuỗi chữ số bằng `0` và rút gọn khoảng trắng đã phát hiện:

- 193 normalized template vượt partition, ảnh hưởng 4.072 dòng;
- tất cả thuộc `fake_profile_post`, không có xung đột nhãn;
- 684/1.591 (42,99%) fake-profile validation và 758/1.590 (47,67%) fake-profile test khớp template đã có trong train.

Trong không gian `char_wb`, 515 validation và 811 test row có nearest-train cosine từ 0,95 trở lên. Riêng test `fake_profile_post` là 770/1.590 row. Sau khi loại 811 row này khỏi phép tính test:

| Representation | Test Macro-F1 đầy đủ | Test Macro-F1 khi similarity < 0,95 |
| --- | ---: | ---: |
| `word_1_2` | 87,26% | 84,20% |
| `word_1_2_plus_char_wb_3_5` | 87,12% | 84,02% |

Normalizer trên chỉ dùng để audit, không được áp dụng như một bước tiền xử lý trên split hiện tại. Nếu thử chuẩn hóa chữ số, emoji hoặc placeholder, phải dựng lại `split_group_id` bằng chính normalizer đó trước khi đánh giá.

## Internal test và leave-one-source-out

| Phép đo | `word_1_2` | `word + char_wb` | Chênh lệch challenger |
| --- | ---: | ---: | ---: |
| Test pooled Macro-F1 | 87,26% | 87,12% | −0,14 điểm % |
| Test source-mean Macro-F1 | 82,96% | 82,53% | −0,43 điểm % |
| Test worst-source Macro-F1 | 49,09% | 49,06% | −0,03 điểm % |
| LOSO mean Macro-F1 | 61,04% | 64,64% | +3,59 điểm % |
| LOSO worst-source Macro-F1 | 32,43% | 44,13% | +11,69 điểm % |

Theo từng nguồn internal test, challenger kém hơn ở `cresci_stock_2018`, `phishing` và `twitter_bot_detection`, đồng hạng ở `fake_profile_post` và `spam_email`; số nguồn cải thiện là 0/5.

LOSO cho thấy một trade-off đáng lưu ý:

| Nguồn bị giữ lại | `word_1_2` Macro-F1 | `word + char_wb` Macro-F1 |
| --- | ---: | ---: |
| `cresci_stock_2018` | 54,28% | 58,42% |
| `fake_profile_post` | 32,43% | 52,50% |
| `phishing` | 86,62% | 87,24% |
| `spam_email` | 86,08% | 80,90% |
| `twitter_bot_detection` | 45,80% | 44,13% |

Challenger chuyển tốt hơn sang ba nguồn nhưng giảm ở hai nguồn. LOSO này fit vocabulary và classifier chỉ trên train của bốn nguồn còn lại; validation không được đưa vào train hoặc tuning.

## Kiểm định ghép cặp theo nhóm

Test có 2.429 dòng nhưng chỉ 1.026 `split_group_id`; nhóm lớn nhất có 127 dòng. Vì các dòng trong cùng nhóm không độc lập, gate dùng 10.000 lượt paired cluster bootstrap theo `split_group_id`, không dùng McNemar từng dòng làm bằng chứng chính.

- Chênh lệch Macro-F1 challenger − baseline: −0,001381.
- Khoảng tin cậy percentile 95%: `[−0,009524; 0,006597]`.
- Xác suất bootstrap challenger tốt hơn 0: 0,364.

Khoảng tin cậy chứa 0 và điểm ước lượng nghiêng về baseline.

## Quyết định

- Giữ `ISI_TEXT_BASELINE_V1` làm baseline nội bộ.
- `word + char_wb` không đạt research-candidate gate và không được promote.
- Giữ LOSO improvement như bằng chứng cho hướng nghiên cứu character robustness, không diễn giải là model tốt hơn tổng thể.
- Không triển khai, không dùng score như xác suất lừa đảo thực tế và không gọi label 1 là fraud đã xác minh.
- Gate tiếp theo là xây lại split bằng normalizer định dùng và đánh giá trên external/curated evidence set chưa từng được mở để chọn model.

## Tái lập

```powershell
.venv\Scripts\python.exe scripts\analyze_mendeley_text_representation_ablation.py `
  --input 'D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\mendeley_v2_group_split.csv' `
  --output-dir 'D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\text_representation_ablation_reproduction' `
  --run-at '2026-09-15T08:11:11.092099+00:00'
```

Script từ chối ghi đè artifact mặc định. Kiểm tra registry, hash, split rows, prediction, baseline và decision bằng:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_text_representation_ablation_registry.py
```

Hai artifact lớn nằm ngoài Git tại `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\text_representation_ablation_v1`.
