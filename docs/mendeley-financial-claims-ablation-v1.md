# Financial Claims V4 presence ablation V1

## Kết luận

Giữ nguyên `ISI_TEXT_BASELINE_V2`. Việc thêm 11 cờ có/không của Financial
Claims V4 không cải thiện validation theo protocol đã khóa và làm Macro-F1 của
nguồn phishing giảm 2,5866 điểm phần trăm. Challenger không được promote và
không được mở trên test.

Đây là kết quả âm nhưng hữu ích: feature extraction vẫn có giá trị để giải
thích và audit nội dung, song chưa chứng minh được lợi ích dự đoán bổ sung cho
baseline text hiện tại.

## Protocol khóa trước khi chạy

Protocol được lưu tại
`configs/mendeley_financial_claims_ablation_v1_protocol.json`, SHA-256:

`e9fa5fa6dbcdf51e93671f327af5606141a7b1fd639102cf52f6eadb43555de2`

Thiết kế chỉ có một challenger hợp lệ để hạn chế chọn theo kết quả:

1. `text_only`: baseline word TF-IDF + Logistic Regression đã khóa.
2. `text_plus_financial_claim_presence`: baseline cộng đúng 11 cờ boolean V4.
3. `financial_claim_presence_only`: diagnostic-only, không được promotion.

Không dùng các count, số tiền, phần trăm, evidence span, review decision,
source dataset hoặc metadata. Cờ boolean được nối trực tiếp vào ma trận TF-IDF,
không scaler, không weighting và không chuẩn hóa lại sau khi nối. Classifier,
`C=2.0`, threshold `0.5` và toàn bộ cấu hình text giữ nguyên baseline V2.

## Phạm vi dữ liệu

- Fit vectorizer và classifier: 3.916 dòng train.
- Chọn biến thể: 838 dòng validation.
- Test được mở: 0 dòng.
- Auxiliary được dùng: 0 dòng.
- Quarantine được dùng: 0 dòng.
- Feature coverage khớp đúng toàn bộ train + validation.

Script xác minh hash của protocol, split và feature artifact trước khi chạy,
sau đó kiểm tra các file không đổi trong quá trình selection.

## Gate promotion

Challenger phải đồng thời:

1. Tăng ít nhất 0,01 absolute trên trung bình Macro-F1 của bốn nguồn.
2. Không giảm Macro-F1 của nguồn kém nhất.
3. Không giảm pooled Macro-F1.
4. Không làm bất kỳ nguồn nào giảm quá 0,01 Macro-F1.

Nếu trượt một gate, protocol bắt buộc giữ `text_only` và không mở test.

## Kết quả validation

| Biến thể | Pooled Macro-F1 | Source-mean Macro-F1 | Worst-source Macro-F1 | ROC-AUC |
| --- | ---: | ---: | ---: | ---: |
| Text only | 0,700118 | 0,778049 | 0,480842 | 0,797478 |
| Text + claim presence | 0,698788 | 0,777705 | 0,480947 | 0,797923 |
| Claim presence only | 0,362593 | 0,376215 | 0,276011 | 0,508475 |

Chênh lệch challenger so với baseline:

| Phép đo | Chênh lệch |
| --- | ---: |
| Source-mean Macro-F1 | -0,000344 |
| Pooled Macro-F1 | -0,001330 |
| Worst-source Macro-F1 | +0,000105 |
| Cresci stock Macro-F1 | +0,008729 |
| Phishing Macro-F1 | -0,025866 |
| Spam email Macro-F1 | +0,015655 |
| Twitter bot Macro-F1 | +0,000105 |

Challenger trượt ba gate: không tăng 0,01 ở metric chính, pooled Macro-F1 giảm
và phishing giảm quá giới hạn 0,01. Việc ROC-AUC tăng rất nhẹ không thay đổi
quyết định vì ROC-AUC không phải metric chọn đã khai báo trước.

Model chỉ dùng claim presence có ROC-AUC 0,508475 và pooled Macro-F1 0,362593,
gần mức không có khả năng phân biệt hữu ích. Kết quả diagnostic này không được
dùng để đổi threshold hoặc tạo thêm candidate sau khi đã nhìn validation.

## Giới hạn độ phủ

Bốn cờ không xuất hiện lần nào trong validation:

- `has_return_multiple`
- `has_recruitment_reward`
- `has_payment_or_transfer_request`
- `has_advance_fee_or_withdrawal`

Riêng `has_advance_fee_or_withdrawal` cũng không xuất hiện trong train. Vì vậy
thí nghiệm này không thể ước lượng đáng tin cậy utility riêng của các tín hiệu
đó. Đây là giới hạn của benchmark bốn nguồn, không phải bằng chứng rằng các tín
hiệu không có ích trong dữ liệu thực tế.

## Tái lập và artifact

Hai lần chạy với cùng timestamp tạo cùng SHA-256 selection artifact:

`391649445e476e39e7ffadc1552ca0c872312d503d3e92ccc569d56bb0d627b2`

Artifact được lưu tại:

`D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\financial_claims_ablation_v1\validation_selection_v1.json`

Registry đóng băng:
`registry/models/mendeley_financial_claims_ablation_v1.json`.

## Quyết định tiếp theo

Không mở test cho challenger này. Giữ Financial Claims V4 như feature giải
thích/audit, không đưa vào baseline dự đoán hiện tại. Nếu sau này thử một cách
tích hợp khác, cần giả thuyết và protocol mới; ưu tiên nested validation hoặc dữ
liệu evidence-backed mới thay vì tiếp tục tối ưu trên cùng validation.
