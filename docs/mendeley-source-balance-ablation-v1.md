# Mendeley Source-Balance Ablation V1

## Kết luận

Không thay đổi baseline text hiện tại. Khi chọn chiến lược bằng trung bình Macro-F1 theo nguồn trên validation, mô hình không trọng số vẫn đứng đầu. Cân bằng nguồn đầy đủ cải thiện leave-one-source-out nhưng làm giảm mạnh validation và internal test. Không có chiến lược nào tốt hơn một cách đồng thời và ổn định.

## Câu hỏi thí nghiệm

Train của Mendeley `group_split_v1` có 11.344 bản ghi nhưng phân bố nguồn rất lệch:

| Nguồn | Số bản ghi train | Tỷ trọng |
| --- | ---: | ---: |
| `fake_profile_post` | 7.426 | 65,46% |
| `twitter_bot_detection` | 1.856 | 16,36% |
| `spam_email` | 777 | 6,85% |
| `phishing` | 740 | 6,52% |
| `cresci_stock_2018` | 545 | 4,80% |

Phép thử hỏi liệu giảm ảnh hưởng của nguồn lớn nhất có giúp model tổng quát sang nguồn chưa thấy hay không.

`source_dataset` chỉ được dùng để tính trọng số trên train và chia báo cáo theo nguồn. Nó không được mã hóa vào TF-IDF và không nằm trong feature matrix.

## Thiết kế đã khóa trước khi mở test

Giữ nguyên cấu hình baseline: TF-IDF word unigram/bigram và Logistic Regression `C=2`, `class_weight=None`, ngưỡng 0,5. Không tune lại model để tránh trộn tác động của trọng số với thay đổi hyperparameter.

Năm chiến lược:

1. Không trọng số.
2. Trọng số tỷ lệ nghịch căn bậc hai tần suất nguồn.
3. Trọng số tỷ lệ nghịch tần suất nguồn.
4. Trọng số tỷ lệ nghịch căn bậc hai tần suất từng cặp nguồn–nhãn.
5. Trọng số tỷ lệ nghịch tần suất từng cặp nguồn–nhãn.

Mọi vector trọng số được chuẩn hóa về trung bình 1. Chiến lược được chọn bằng trung bình Macro-F1 của năm nguồn trên validation; tie-break lần lượt bằng nguồn kém nhất, pooled Macro-F1, F1 label 1 và chiến lược đơn giản hơn. Test không tham gia fit TF-IDF, fit model hoặc chọn chiến lược.

## Kết quả

| Chiến lược | Effective train N | Validation source-mean Macro-F1 | Validation worst-source Macro-F1 | Test Macro-F1 | LOSO mean Macro-F1 | LOSO worst-source Macro-F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Không trọng số | 11.344,0 | 83,61% | 50,40% | 87,26% | 61,04% | 32,43% |
| Căn bậc hai inverse-source | 8.626,1 | 77,90% | 51,41% | 79,68% | 62,14% | 37,67% |
| Inverse-source | 4.857,5 | 78,40% | 52,72% | 79,54% | 63,14% | 40,98% |
| Căn bậc hai inverse-source-label | 8.003,2 | 77,90% | 51,31% | 79,79% | 62,74% | 38,31% |
| Inverse-source-label | 4.354,4 | 77,83% | 51,35% | 87,79% | 61,04% | 37,11% |

Validation chọn lại chiến lược **không trọng số**.

## Ý nghĩa của trade-off

Inverse-source làm tổng trọng số của mỗi nguồn bằng đúng 2.268,8. Nó cải thiện leave-one-source-out mean Macro-F1 từ 61,04% lên 63,14% và nguồn kém nhất từ 32,43% lên 40,98%. Tuy nhiên test Macro-F1 giảm từ 87,26% xuống 79,54%. Trên test ghép cặp, nó sửa 15 lỗi nhưng tạo thêm 139 lỗi mới (`p = 2,41e-26`).

Nguyên nhân chính là mất hiệu năng trên `fake_profile_post`: Macro-F1 validation giảm từ 100% xuống 69,30%; test giảm xuống 78,81%. Lợi ích ở Twitter bot và một số nguồn leave-one-out không đủ bù lại.

Inverse-source-label có test Macro-F1 87,79%, cao hơn không trọng số 0,53 điểm phần trăm. Tuy nhiên:

- validation source-mean Macro-F1 thấp hơn 5,78 điểm phần trăm;
- leave-one-source-out mean gần như không đổi: 61,0443% so với 61,0438%;
- chỉ giảm 8 lỗi ròng trên test và McNemar `p = 0,256`, không có ý nghĩa thống kê;
- effective sample size chỉ còn 4.354,4/11.344, cho thấy trọng số rất tập trung.

Không được chọn biến thể này sau khi nhìn test.

## Quyết định

- Giữ `ISI_TEXT_BASELINE_V1` không trọng số làm baseline nội bộ.
- Không promote bất kỳ chiến lược source balancing nào.
- Ghi nhận inverse-source như một robustness trade-off: tốt hơn khi loại cả nguồn, kém hơn rõ rệt trên phân bố nội bộ.
- Source imbalance không phải nguyên nhân duy nhất của generalization gap; dữ liệu giữa các nguồn còn khác về nhiệm vụ, cách gán nhãn và kiểu nội dung.
- Không dùng score làm xác suất lừa đảo thực tế và không triển khai cho quyết định chặn/xử phạt.

## Tái lập

```powershell
.venv\Scripts\python.exe scripts\analyze_mendeley_source_balance_ablation.py `
  --input 'D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\mendeley_v2_group_split.csv' `
  --output-dir 'D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\source_balance_ablation_reproduction' `
  --run-at '2026-09-15T07:45:33.586078+00:00'
```

Không chạy đè lên `source_balance_ablation_v1`; script từ chối ghi đè mặc định.

Kiểm tra registry, hash, trọng số, baseline và prediction:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_source_balance_ablation_registry.py
```

Artifact lớn nằm ngoài Git tại `D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v1\source_balance_ablation_v1`.
