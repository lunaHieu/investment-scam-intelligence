# Phân tích lỗi Text Baseline V2

## Mục đích

Phân tích này trả lời câu hỏi: model V2 sai ở đâu và các mẫu sai có đặc điểm gì. Đây là bước chẩn đoán sau khi test đã được mở, không phải một vòng chọn model mới.

Model, word TF-IDF, `C=2.0`, threshold `0.5` và feature policy `text_content only` đều giữ nguyên. Script không gọi `fit`, không dùng auxiliary/quarantine, không truy cập mạng và không tạo nhãn mới.

## Kết quả chính

Test có 838 mẫu. Model đúng 592 và sai 246, gồm 118 false positives và 128 false negatives.

| Nguồn | Test | Lỗi | Tỷ lệ lỗi | FP | FN | Macro-F1 | ROC-AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cresci_stock_2018` | 116 | 19 | 16,38% | 6 | 13 | 0,8362 | 0,8949 |
| `phishing` | 158 | 15 | 9,49% | 2 | 13 | 0,9007 | 0,9804 |
| `spam_email` | 166 | 4 | 2,41% | 1 | 3 | 0,9691 | 0,9936 |
| `twitter_bot_detection` | 398 | 208 | 52,26% | 109 | 99 | 0,4761 | 0,4564 |

`twitter_bot_detection` chiếm 208/246 lỗi, tương đương 84,55%. ROC-AUC 0,4564 cho nguồn này cho thấy thứ hạng score còn tệ hơn mức ngẫu nhiên trên riêng domain đó; không được giải quyết bằng cách đổi threshold trên chính test này.

## Đặc điểm của lỗi

- 192/246 lỗi có tối đa 12 surface tokens. Median của nhóm lỗi là 11 tokens, so với 28 ở nhóm dự đoán đúng.
- Median vocabulary coverage của lỗi là 0,5294, thấp hơn 0,6430 ở nhóm đúng. Coverage ở đây là tỷ lệ unigram/bigram duy nhất do analyzer sinh ra có mặt trong vocabulary đã đóng băng.
- Median cosine similarity với mẫu gần nhất trong train+validation là 0,2649 ở nhóm lỗi và 0,2880 ở nhóm đúng. Chênh lệch tồn tại nhưng nhỏ; similarity chỉ là chỉ báo mô tả, không phải bằng chứng trùng lặp hay nguyên nhân sai.
- 212/246 lỗi có confidence dưới 0,75. Chỉ 1 lỗi đạt confidence từ 0,90 trở lên. Vì vậy phần lớn lỗi nằm gần ranh giới quyết định, thay vì là một khối lớn các lỗi cực kỳ tự tin.
- Brier score là 0,175458 và fixed-bin ECE là 0,050590, đều đo với nhãn nguồn nội bộ. Chúng không biến score thành xác suất lừa đảo ngoài thực tế.
- 246 lỗi thuộc 245 `split_group_id`; chỉ một group có hai lỗi. Review queue giữ mỗi group tối đa một mẫu.

## Review queue dùng để làm gì

Tệp `text_baseline_v2_error_review_queue.jsonl` có 44 mẫu. Queue lấy tối đa 8 group có confidence cao nhất cho mỗi tổ hợp `source_dataset × false_positive/false_negative`. Những strata có ít hơn 8 lỗi được giữ toàn bộ.

Mỗi dòng có:

- nhãn nguồn và dự đoán của model;
- score/confidence cố định;
- độ dài, vocabulary coverage và mẫu train/validation gần nhất trong không gian TF-IDF;
- các feature đóng góp nhiều nhất về label 0 hoặc 1;
- excerpt tối đa 240 ký tự, đã che email, URL, số điện thoại và chuỗi định danh dài.

Người review chỉ cần ghi nhận dạng failure mode, ví dụ `quá ngắn/thiếu ngữ cảnh`, `từ khóa tài chính gây nhầm`, `văn phong đặc thù nguồn`, hoặc `nhãn nguồn có vẻ không đồng nhất`. Không sửa raw label, không tạo Gold label và không dùng queue để chọn threshold/model.

## Kiểm soát sai sót

Script từ chối chạy nếu hash của split, model, results hoặc predictions khác registry. Nó tải lại model, tái tạo đủ 838 probability/prediction, đối chiếu toàn bộ metrics đã công bố, rồi kiểm tra model hash một lần nữa.

Hai artifact chính thức đã tái tạo bit-for-bit:

| Artifact | SHA-256 |
| --- | --- |
| `text_baseline_v2_error_analysis.json` | `d53e9c958345f9f0b2dac4e6b08252ea6d20efcde6d9b98da99f60db269466bd` |
| `text_baseline_v2_error_review_queue.jsonl` | `1e905e2b90dae1ca4a3d106a433e8e53745e3e25e64068ac9ee2e548a2970cef` |

Kiểm tra độc lập bằng:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_text_baseline_v2_error_analysis_registry.py
```

## Quyết định

Giữ nguyên Text Baseline V2 làm baseline nội bộ tái lập được, nhưng tiếp tục chặn deployment. Không tối ưu lại từ test V2. Gate kế tiếp là đánh giá nguyên cấu hình đã đóng băng trên curated cases có evidence độc lập hoặc một external dataset thật sự chưa dùng trong quá trình phát triển.
