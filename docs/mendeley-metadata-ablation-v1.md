# Mendeley Metadata Ablation V1

## Kết luận

Không đưa metadata của Mendeley V2 vào baseline chính. Không có biến thể text + metadata nào đồng thời vượt text-only trên cả internal test và leave-one-source-out. Mẫu thiếu metadata còn nhận diện nguồn dữ liệu với độ chính xác 93,45% và Macro-F1 73,52% trên test, cho thấy nguy cơ model học nguồn thay vì học dấu hiệu lừa đảo.

Baseline chính vẫn là `ISI_TEXT_BASELINE_V1`. Kết luận này chỉ áp dụng cho cấu trúc metadata hiện tại của Mendeley V2; không có nghĩa metadata hành vi nói chung là vô ích.

## Phạm vi dữ liệu

- Input: Mendeley `group_split_v1`, 16.202 bản ghi.
- Train: 11.344; validation: 2.429; internal test: 2.429.
- `split_group_id` đi qua nhiều partition: 0.
- SHA-256 input: `0f540f838dc0050c2cc1f8f8d98c4239acaba1ad0d1407066f1a578e5acdb2ff`.
- Đây là internal test theo nhãn nguồn Mendeley, không phải Gold test và không phải ground truth lừa đảo đã được cơ quan quản lý xác minh.

Raw và split chỉ được đọc. Không có file raw nào bị sửa và không có network operation.

## Thiết kế thí nghiệm

Chín biến thể dùng cùng một group split và cùng họ mô hình Logistic Regression:

1. Text-only.
2. Chỉ metadata hành vi/tài khoản.
3. Chỉ thống kê nội dung.
4. Toàn bộ metadata, chỉ giá trị.
5. Toàn bộ metadata, thêm cờ thiếu dữ liệu.
6. Text + metadata hành vi/tài khoản.
7. Text + thống kê nội dung.
8. Text + toàn bộ metadata, chỉ giá trị.
9. Text + toàn bộ metadata, thêm cờ thiếu dữ liệu.

Nhóm hành vi/tài khoản gồm followers, following, số bài, tuổi tài khoản, repost, các tỷ lệ tương tác và sáu cờ profile. Nhóm thống kê nội dung gồm số mention, hashtag, độ dài, số từ và hai tỷ lệ tải mention/hashtag.

Các trường `source_dataset`, `source_modality`, `has_metadata`, `label`, `partition`, `gate_path`, các điểm gate, `original_partition` và `split_group_id` không được dùng làm predictive feature.

Mỗi biến thể chọn `C` và `class_weight` bằng validation F1 label 1; test không tham gia fit feature, chọn tham số hoặc chọn biến thể. Sau khi khóa cấu hình, test được đánh giá một lần. Leave-one-source-out giữ nguyên tham số đã chọn rồi học lại sau khi loại hoàn toàn từng nguồn khỏi train.

## Kết quả chính

| Biến thể | Validation F1-1 | Test F1-1 | Test Macro-F1 | Test balanced accuracy | LOSO Macro-F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text-only | 93,35% | 93,12% | 87,26% | 87,19% | 61,04% |
| Account metadata only | 84,51% | 85,69% | 72,85% | 72,46% | 41,43% |
| Content statistics only | 85,12% | 84,59% | 60,68% | 59,94% | 41,71% |
| All metadata, values | 87,18% | 89,49% | 80,22% | 79,86% | 49,00% |
| All metadata + missingness | 84,39% | 90,59% | 82,55% | 82,45% | 46,09% |
| Text + account metadata | 92,79% | 91,57% | 83,34% | 82,00% | 64,87% |
| Text + content statistics | 93,45% | 89,96% | 79,38% | 77,60% | 60,45% |
| Text + all metadata, values | 92,44% | 91,08% | 82,15% | 80,60% | 57,84% |
| Text + all metadata + missingness | 92,09% | 92,38% | 85,48% | 84,79% | 63,95% |

Validation chọn `text_plus_content_statistics_values`, nhưng mức tăng F1-1 so với text-only chỉ là 0,09 điểm phần trăm. Trên internal test, biến thể này làm giảm 125 lỗi ròng theo chiều xấu: sửa được 23 lỗi của text-only nhưng tạo thêm 148 lỗi mới. McNemar exact hai phía có `p = 1,48e-23`.

Sự giảm này tập trung mạnh ở nguồn `fake_profile_post`: trên validation biến thể kết hợp không có lỗi, nhưng trên test nó đổi sai 127/231 bản ghi label 0 thành label 1. ROC-AUC test vẫn là 95,45%, gần text-only 95,83%, trong khi Macro-F1 tại ngưỡng cố định 0,5 giảm mạnh. Điều này cho thấy ranking còn tốt nhưng calibration/quyết định lớp không ổn định qua partition. Không chỉnh threshold theo test để che sự lệch này.

Hai biến thể có metadata tài khoản cải thiện trung bình Macro-F1 leave-one-source-out, nhưng lại giảm đáng kể Macro-F1 trên internal test. Khi loại riêng nguồn Twitter bot, các biến thể account/all metadata dự đoán toàn bộ về một lớp và có F1 label 1 bằng 0. Kết quả thay đổi mạnh theo nguồn nên chưa đủ ổn định để thay baseline.

## Kiểm tra học tắt từ missingness

Trong 20 cột metadata, chỉ `content_length` và `word_count` đầy đủ toàn bộ. Các cột còn lại thiếu theo những khối đặc trưng của từng nguồn:

- Phishing và spam email: thiếu cùng lúc 18 cột metadata.
- Twitter bot: thiếu một nhóm cố định liên quan following, số bài, tỷ lệ follower/following, bio, URL, private và ảnh profile mặc định.
- Fake profile: đủ toàn bộ metadata.
- Cresci stock: đủ phần lớn, nhưng thiếu một phần repost, tỷ lệ tương tác/follower, follower/following và URL.

Chỉ dùng vector 20 bit cho biết cột nào bị thiếu, ánh xạ majority trên train đã đạt:

| Chẩn đoán nguồn từ missingness | Validation | Test |
| --- | ---: | ---: |
| Accuracy | 93,50% | 93,45% |
| Macro-F1 | 73,58% | 73,52% |
| Balanced accuracy | 80,00% | 80,00% |

Baseline luôn đoán nguồn đông nhất chỉ đạt 65,46% accuracy, 15,82% Macro-F1 và 20,00% balanced accuracy trên test. Missingness nhận đúng gần như tuyệt đối Cresci, fake profile và Twitter bot; nó chỉ không phân biệt được phishing với spam email vì hai nguồn có cùng mẫu thiếu.

Ngoài ra, chỉ dùng nguồn để chọn lớp majority của từng nguồn đã đạt 76,04% accuracy trên test. Source identity có liên hệ mạnh với label, nên model có thể đạt điểm cao bằng cách nhận diện nguồn. Chẩn đoán này dùng `source_dataset` làm target phân tích riêng; trường đó không đi vào bất kỳ model dự đoán label nào.

## Quyết định

- Không promote metadata vào baseline chính.
- Giữ text-only làm baseline nội bộ đã đóng băng.
- Giữ metadata ablation làm bằng chứng nghiên cứu về source confounding và dataset shift.
- Không dùng các score này như xác suất lừa đảo thực tế và không triển khai để chặn, xử phạt hoặc đưa ra quyết định tài chính.
- Chỉ xem xét lại metadata khi có dữ liệu được đo nhất quán giữa các nguồn, sau đó lặp lại group split và leave-one-source-out theo kế hoạch định trước.

## Tái lập và kiểm tra

Chạy thí nghiệm:

```powershell
.venv\Scripts\python.exe scripts\analyze_mendeley_metadata_ablation.py `
  --input 'D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\mendeley_v2_group_split.csv' `
  --output-dir 'D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\metadata_ablation_reproduction' `
  --run-at '2026-09-14T09:37:15.556935+00:00'
```

Không chạy đè lên `metadata_ablation_v1`. Script từ chối ghi đè mặc định; `--overwrite` chỉ dành cho trường hợp cố ý thay artifact chưa đóng băng.

Kiểm tra hash, số dòng prediction và khả năng tái lập baseline text:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_metadata_ablation_registry.py
```

Artifact lớn được lưu ngoài Git tại:

- `metadata_ablation_results_v1.json`: kết quả đầy đủ của 9 biến thể, theo nguồn và leave-one-source-out.
- `metadata_ablation_test_predictions_v1.jsonl`: 2.429 prediction ghép cặp để kiểm tra sai số.

Registry đóng băng: `registry/models/mendeley_metadata_ablation_v1.json`.
