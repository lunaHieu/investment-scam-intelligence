# So sánh hai baseline text — Mendeley group split V1

## Kết luận

TF-IDF + Logistic Regression được chọn làm baseline nội bộ mạnh hơn. Cả hai model dùng đúng cùng group split, chỉ nhận `text_content`, và không dùng test để chọn tham số. Kết quả này vẫn là benchmark theo nhãn Mendeley, không phải khả năng xác minh lừa đảo thực tế.

## Cùng một test cố định

| Model | Accuracy | F1 label 1 | Macro-F1 | Balanced accuracy |
| --- | ---: | ---: | ---: | ---: |
| Naive Bayes | 89.5% | 92.7% | 87.0% | 87.9% |
| TF-IDF + Logistic Regression | 90.0% | 93.1% | 87.3% | 87.2% |

Mức tăng F1 label 1 chỉ khoảng 0,46 điểm phần trăm; cải thiện trong test quen thuộc là nhỏ.

## Test cố định theo nguồn (F1 label 1)

| Nguồn | Naive Bayes | TF-IDF LogReg | Chênh lệch |
| --- | ---: | ---: | ---: |
| cresci_stock_2018 | 69.8% | 75.6% | +5.9% |
| fake_profile_post | 100.0% | 100.0% | +0.0% |
| phishing | 96.4% | 95.6% | -0.8% |
| spam_email | 86.1% | 95.3% | +9.3% |
| twitter_bot_detection | 45.8% | 51.9% | +6.1% |

## Leave-one-source-out (F1 label 1)

| Nguồn bị loại hoàn toàn khỏi train | Naive Bayes | TF-IDF LogReg | Chênh lệch |
| --- | ---: | ---: | ---: |
| cresci_stock_2018 | 57.4% | 55.5% | -1.9% |
| fake_profile_post | 92.2% | 47.9% | -44.3% |
| phishing | 61.2% | 89.9% | +28.7% |
| spam_email | 4.3% | 79.5% | +75.2% |
| twitter_bot_detection | 34.0% | 30.3% | -3.7% |

Trung bình F1 label 1 qua năm nguồn tăng từ 49.8% lên 60.6%. Tuy nhiên fake-profile giảm mạnh và Twitter bot vẫn gần mức ngẫu nhiên. Không model nào tổng quát ổn định trên mọi nguồn.

## Quyết định cho đề tài

- Giữ Naive Bayes làm baseline tối giản để tái lập.
- Dùng TF-IDF + Logistic Regression làm baseline nội bộ chính.
- Không gọi output là xác suất lừa đảo và chưa triển khai cho người dùng.
- Bước đánh giá quyết định vẫn là curated/external cases có evidence độc lập.

## Trạng thái đóng băng

Text baseline V1 được đóng băng ngày 2026-09-12. Registry ghi đầy đủ hash của
split, model, kết quả, phiên bản runtime và giới hạn sử dụng tại
`registry/models/text_baseline_v1.json`. Test V1 từ thời điểm này chỉ dùng để
báo cáo; không tiếp tục chọn feature, threshold hoặc model bằng test đó.
