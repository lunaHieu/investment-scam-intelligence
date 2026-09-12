# Báo cáo baseline văn bản — ISI V1

## Kết luận ngắn — đã hiệu chỉnh sau leakage audit

Baseline đầu tiên **đã chạy thành công về mặt kỹ thuật**: mô hình phân loại văn
bản đạt F1 **90,6%** trên test split do Mendeley V2 cung cấp. Tuy nhiên, đây
chỉ là kết quả trên nhãn benchmark "investment-related deceptive or suspicious
content" của nguồn Mendeley; nó không chứng minh mô hình có thể kết luận một
nội dung là lừa đảo đầu tư trong thực tế.

Audit ngày 2026-09-11 phát hiện **1.126/2.090 mẫu test (53,9%)** có nội dung
sau chuẩn hóa trùng với train. Sau khi loại các mẫu này khỏi phép đo, test chỉ
còn 964 mẫu và F1 giảm xuống **74,4%**. Do đó, 90,6% là kết quả benchmark bị
ảnh hưởng mạnh bởi leakage; 74,4% là phép đo chẩn đoán sạch hơn nhưng vẫn chưa
phải external test độc lập.

Baseline hiện được giữ ở vai trò **mốc đối chiếu kỹ thuật**, không được dùng để
phát hành cảnh báo hay làm tuyên bố hiệu năng chính của đề tài.

## Thiết lập thí nghiệm

| Hạng mục | Giá trị |
| --- | --- |
| Dữ liệu | Mendeley V2, 16.202 records; dùng split train/validation/test sẵn có |
| Đầu vào | Chỉ `text_content` |
| Không đưa vào model | source ID, partition, metadata, filter score, evidence, review status |
| Mô hình | Multinomial Naive Bayes (text-only, dependency-free) |
| Train | 11.370 records |
| Validation | 2.742 records |
| Test | 2.090 records |
| Vocabulary | 12.540 tokens |

## Kết quả chính

`label 1` dưới đây là nhãn benchmark của Mendeley, không phải phán quyết pháp
lý hay ground truth lừa đảo đầu tư.

| Split | Accuracy | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Validation | 90,6% | 94,8% | 93,0% | 93,9% |
| Test | 86,9% | 91,0% | 90,1% | **90,6%** |

Test confusion matrix: 1.310 true positives, 507 true negatives, 129 false
positives, 144 false negatives.

## Kết quả leakage audit

Chuẩn hóa ở đây chỉ thống nhất Unicode, chữ hoa/thường, dấu câu và khoảng
trắng. Đây là exact duplicate sau chuẩn hóa, không phải một mô hình đo tương
đồng mơ hồ.

| Hạng mục | Kết quả |
| --- | ---: |
| Cross-split duplicate groups | 1.434 |
| Train-to-evaluation duplicate groups | 1.369 |
| Validation rows trùng train | 1.725 / 2.742 |
| Test rows trùng train | 1.126 / 2.090 |
| Tổng evaluation rows trùng train | 2.851 / 4.832 |
| Duplicate groups có nhãn mâu thuẫn | 1 |

Phân bố 2.851 evaluation rows trùng train theo nguồn: `fake_profile_post`
2.789, `phishing` 39, `spam_email` 17, `cresci_stock_2018` 6. Điều này giải
thích vì sao nhóm `fake_profile_post` trước đó đạt F1 gần 100%.

| Split sau loại exact-overlap với train | Số mẫu còn lại | Accuracy | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Validation | 1.017 | 75,2% | 81,8% | 76,5% | 79,1% |
| Test | 964 | 72,1% | 75,5% | 73,4% | **74,4%** |

Audit còn tạo nhóm `template_candidate` bằng cách che URL, email, handle và
con số. Nó phát hiện 3.040 evaluation rows có candidate giống train. Con số
này chỉ dùng để tìm mẫu cần review, không được coi là duplicate chắc chắn.

## Baseline trên group split mới

Toàn bộ 16.202 records được nhóm lại trước khi chia. Một nhóm chứa các bản ghi
trùng exact sau chuẩn hóa hoặc cùng template sau khi che URL, email, handle và
con số. Mỗi nhóm chỉ được phép nằm trong một partition.

| Thuộc tính split mới | Giá trị |
| --- | ---: |
| Số nhóm | 6.848 |
| Nhóm lớn nhất | 398 records |
| Train | 11.344 (70,02%) |
| Validation | 2.429 (14,99%) |
| Test | 2.429 (14,99%) |
| Exact-normalized groups nằm chéo split | **0** |
| Template-candidate groups nằm chéo split | **0** |

Train lại cùng mô hình trên split mới cho validation F1 91,5% và test F1
**92,7%**. Kết quả cao này không mâu thuẫn với F1 74,4% ở phần trên: 74,4% là
phần còn lại của test cũ sau khi bỏ overlap (một subset có phân bố bị thay đổi),
còn 92,7% là phép chia lại toàn bộ dữ liệu theo nhóm.

Dù không còn nhóm trùng chéo split, phép kiểm tra bỏ hẳn từng nguồn vẫn cho F1:
`fake_profile_post` 92,2%, `phishing` 61,2%, `cresci_stock_2018` 57,4%,
`twitter_bot_detection` 34,0%, `spam_email` 4,3%. Vì vậy kết luận khoa học vẫn
là: baseline học tốt pattern nội bộ nhưng chưa generalize ổn định sang nguồn
mới.

## Kiểm tra độ bền theo nguồn

Đây là phép đo quan trọng hơn con số tổng: model được train trên toàn bộ train
split và đo F1 từng `source_dataset` ở test. `source_dataset` chỉ dùng để báo
cáo, không hề là feature.

| Nhóm nguồn test | Số records | F1 |
| --- | ---: | ---: |
| fake_profile_post | 1.259 | 99,9% |
| phishing | 151 | 93,5% |
| spam_email | 168 | 85,7% |
| cresci_stock_2018 | 115 | 68,8% |
| twitter_bot_detection | 397 | 44,6% |

Kết quả gần 100% ở `fake_profile_post` cùng kết quả rất thấp ở
`twitter_bot_detection` là dấu hiệu mô hình có thể học đặc trưng riêng của
nguồn, thay vì hiểu khái niệm lừa đảo đầu tư một cách tổng quát.

## Kiểm tra chéo nguồn

Ở phép thử nghiêm hơn, toàn bộ một nhóm nguồn bị giữ lại khỏi train. F1 giảm:

| Nhóm bị giữ lại | F1 cross-source |
| --- | ---: |
| fake_profile_post | 91,8% |
| cresci_stock_2018 | 64,2% |
| phishing | 61,1% |
| twitter_bot_detection | 35,9% |
| spam_email | 8,7% |

Điều này xác nhận mô hình **chưa đủ khả năng generalize** sang dữ liệu mới.
Con số 90,6% chỉ dùng để tái lập benchmark ban đầu. Con số 74,4% dùng để chẩn
đoán sau khi lọc exact-overlap, nhưng cũng không được dùng làm tuyên bố hiệu
năng cho ISI V1 hoàn chỉnh vì test vẫn cùng nguồn và chưa group-split lại.

## Bước cải thiện có ý nghĩa

1. Có curated cases với evidence độc lập, đặc biệt mẫu tiếng Việt và các lời
   mời đầu tư thực tế.
2. Tách train/test theo case, campaign, domain family và near-duplicate, thay
   vì chỉ theo dòng dữ liệu.
3. So sánh baseline này với mô hình text mạnh hơn sau khi có labels đủ tin cậy.
4. Báo cáo F1 theo nguồn và cross-source ở mọi thử nghiệm sau, không chỉ báo
   cáo một F1 tổng.

## Tái lập kết quả

Raw data: `D:\nckh 2026-2027\ISI_Data\raw\mendeley_investment_deceptive_2026\v2\Multimodal_Dataset_for_Investment-Related_Deceptive_Content_Detection_on_Social_Platforms.csv`

Kết quả gốc: `D:\nckh 2026-2027\ISI_Data\derived\mendeley_text_baseline\`

Group split và baseline mới:
`D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\`

```powershell
python scripts\train_mendeley_text_baseline.py --input "D:\nckh 2026-2027\ISI_Data\raw\mendeley_investment_deceptive_2026\v2\Multimodal_Dataset_for_Investment-Related_Deceptive_Content_Detection_on_Social_Platforms.csv" --output-dir outputs\mendeley_text_baseline
python scripts\evaluate_mendeley_baseline_by_source.py --input "D:\nckh 2026-2027\ISI_Data\raw\mendeley_investment_deceptive_2026\v2\Multimodal_Dataset_for_Investment-Related_Deceptive_Content_Detection_on_Social_Platforms.csv" --model "D:\nckh 2026-2027\ISI_Data\derived\mendeley_text_baseline\model.json"
python scripts\audit_mendeley_text_overlap.py --input "D:\nckh 2026-2027\ISI_Data\raw\mendeley_investment_deceptive_2026\v2\Multimodal_Dataset_for_Investment-Related_Deceptive_Content_Detection_on_Social_Platforms.csv" --model "D:\nckh 2026-2027\ISI_Data\derived\mendeley_text_baseline\model.json" --output outputs\mendeley_text_baseline\text_overlap_audit.json
```
