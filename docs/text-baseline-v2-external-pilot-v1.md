# Text Baseline V2 external pilot V1

External pilot này chỉ được chạy sau khi intake validator xác nhận đủ 21 record hợp lệ: 10 `CONFIRMED` và 11 `LEGITIMATE`. Mỗi record có raw capture khớp SHA-256, text hash khớp, evidence đã review, confidence `HIGH` và status `RECONCILED`.

Mô hình được dùng nguyên trạng từ `ISI_TEXT_BASELINE_V2`. Script kiểm tra hash model, metadata, threshold `0.5`, feature policy `text_content only`, fit partitions `train + validation`, và việc loại `auxiliary + quarantine`. Không có model fit, threshold change, vectorizer change hay network operation trong lần chấm external này.

Nhãn external được ánh xạ `LEGITIMATE -> 0` và `CONFIRMED -> 1`. Score label 1 vẫn mang ngữ nghĩa nhãn deceptive/suspicious của benchmark Mendeley; nó không phải xác suất lừa đảo thực tế.

Pilot chỉ có 21 website snapshot và hai nhánh thu thập gần như trùng với hai lớp. Vì vậy metric chỉ dùng để chẩn đoán transfer behavior, không được dùng để tuyên bố hiệu năng tổng quát, tune lại trên pilot hoặc triển khai.

## Kết quả đóng băng

- Accuracy: `0.619048`.
- Balanced accuracy: `0.627273`.
- Macro-F1: `0.611111`.
- ROC-AUC: `0.545455`.
- Confusion matrix: `TN=5, FP=6, FN=2, TP=8`.
- Recall `CONFIRMED`: `0.8`; recall `LEGITIMATE`: `0.454545`.
- 13/21 đúng, 8/21 sai.

Bootstrap 95% interval rất rộng: accuracy `0.380952–0.809524`, balanced accuracy `0.427273–0.816667`, Macro-F1 `0.375286–0.805556`. Vì vậy chưa có cơ sở nói model tổng quát hóa tốt. Lỗi nghiêng về false positive: 6 website hợp pháp bị đẩy sang label 1, trong khi 2 website confirmed bị bỏ sót.

Kết quả này không được dùng để đổi threshold hoặc tune trên chính 21 case. Bước nghiên cứu phù hợp tiếp theo là phân tích lỗi và mở rộng benchmark độc lập, đa nguồn, có second-reviewer; không tối ưu model trực tiếp theo pilot nhỏ này.

