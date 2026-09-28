# Phân tích lỗi external pilot của Text Baseline V2

## Mục đích

Phân tích này giải thích 8/21 dự đoán sai của cấu hình `ISI_TEXT_BASELINE_V2` đã đóng băng. Nó không fit/refit model, không thay vectorizer hay threshold `0.5`, không sửa nhãn, không dùng auxiliary/quarantine và không dùng pilot để chọn cấu hình mới.

Toàn bộ 21 probability và prediction được tái tạo từ model gốc rồi đối chiếu với artifact external pilot. Với từng case, script đo vocabulary coverage, tái dựng probability từ intercept và TF-IDF feature contributions, đồng thời tìm hàng gần nhất trong train+validation chỉ để mô tả độ tương tự. Internal test không được dùng cho phép so sánh này.

## Kết quả chính

- Model đúng 13/21 và sai 8/21: 6 false positive, 2 false negative.
- Model dự đoán label 1 cho 14/21 case.
- 4/8 lỗi nằm trong khoảng 0,10 quanh threshold. Hai false negative đều thuộc nhóm này; không được suy ra rằng chỉ cần đổi threshold là giải quyết được vấn đề.
- False positive có median score label 1 là `0.610067`; false negative có median là `0.450581`.
- False negative có mean unique-vocabulary coverage `0.316102`, thấp hơn false positive `0.574638`. Một case confirmed chỉ đạt coverage khoảng `0.07`, cho thấy biểu diễn word TF-IDF gần như không nhận ra phần lớn từ của trang đó.
- Nearest-neighbor cosine đều thấp: mean `0.153042` cho false positive và `0.155703` cho false negative. Đây là dấu hiệu domain shift, không phải bằng chứng trùng lặp hay nguyên nhân trực tiếp.

## Tám case sai

| Case | Loại lỗi | Score label 1 | Khoảng cách threshold | Vocabulary coverage | Nearest source |
| --- | --- | ---: | ---: | ---: | --- |
| `CASE_CONF_008` | FN | 0.418487 | 0.081513 | 0.56 | `spam_email` |
| `CASE_RESERVE_CONF_008` | FN | 0.482675 | 0.017325 | 0.07 | `cresci_stock_2018` |
| `CASE_LEGIT_005` | FP | 0.644564 | 0.144564 | 0.58 | `spam_email` |
| `CASE_RESERVE_LEGIT_003` | FP | 0.620081 | 0.120081 | 0.59 | `spam_email` |
| `CASE_RESERVE_LEGIT_005` | FP | 0.600053 | 0.100053 | 0.50 | `phishing` |
| `CASE_RESERVE_LEGIT_006` | FP | 0.596188 | 0.096188 | 0.60 | `spam_email` |
| `CASE_RESERVE_LEGIT_007` | FP | 0.590920 | 0.090920 | 0.61 | `spam_email` |
| `CASE_RESERVE_LEGIT_008` | FP | 0.675351 | 0.175351 | 0.57 | `phishing` |

Các feature đóng góp về label 1 xuất hiện lặp lại trong false positive gồm `your`, `you`, `our`, `investing`, `security` và `money`. Các từ `wealth`, `advice`, `management` vẫn tạo counter-evidence về label 0 nhưng không đủ đảo quyết định. Điều này phù hợp với một baseline từ vựng đang nhầm văn phong marketing/tư vấn tài chính hợp pháp với các tín hiệu deceptive trong tập huấn luyện. Đây là mô tả hành vi mô hình, không phải bằng chứng nhân quả.

Ở hai false negative, các token như `markets`, `ai`, `traders`, `investor`, `trade`, `capital`, `crypto` và `forex` đóng góp về label 0. Mẫu confirmed có thể mang văn phong tài chính/thị trường mà baseline từng liên hệ với label 0, trong khi các tín hiệu như `account`, `product`, `your`, `money` chưa đủ mạnh.

## Hạn chế quan trọng nhất

Nhãn và nhánh thu thập bị confound hoàn toàn:

| Nhánh thu thập | CONFIRMED | LEGITIMATE |
| --- | ---: | ---: |
| `wayback_confirmed_capture_2026_09_24` | 10 | 0 |
| `sec_iapd_homepage_capture_2026_09_24` | 0 | 11 |

Vì vậy metric lớp hiện tại không thể phân biệt model đang phản ứng với nội dung liên quan tới nhãn hay với kiểu trang/cách capture của hai nguồn. Đây là lý do không được tune, chọn threshold hoặc tuyên bố khả năng triển khai từ 21 case này.

## Gate kế tiếp

Cần mở rộng benchmark có second reviewer độc lập và có cả `CONFIRMED` lẫn `LEGITIMATE` trong các nguồn/kiểu capture có thể so sánh. Chỉ sau khi có benchmark đó mới quyết định nên cải thiện text representation, thêm feature, đổi model hay giữ baseline.

Verifier bắt buộc kiểm tra đủ 21 diagnostic rows, đúng 8 error rows, hash toàn bộ input/output, confounding, và tất cả gate `no fit/no tuning/no deployment`:

```powershell
.venv\Scripts\python.exe scripts\verify_text_baseline_v2_external_pilot_error_analysis.py --registry registry\analyses\text_baseline_v2_external_pilot_error_analysis_v1.json
```
