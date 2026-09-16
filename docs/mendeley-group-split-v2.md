# Mendeley group split V2

## Kết quả

`MENDELEY_GROUP_SPLIT_V2` là split nội bộ mới cho các thí nghiệm text tiếp theo. Nó được dựng trực tiếp từ raw Mendeley V2 đã pin, không dùng `group_split_v1` làm đầu vào và không thay đổi bất kỳ giá trị nguồn nào ngoài cột `partition` trong bản derived.

Đây **không phải Gold test hoặc external test**. Thiết kế V2 được tạo sau khi kết quả và leakage của V1 đã được xem, nên test V2 chỉ là internal research test.

| Vai trò mới | Số dòng | Ý nghĩa |
| --- | ---: | --- |
| `train` | 3.916 | Fit vectorizer/model mới. |
| `validation` | 838 | Chọn cấu hình/ngưỡng; không fit. |
| `test` | 838 | Chỉ mở sau khi lựa chọn trên validation được đóng băng. |
| `auxiliary` | 10.607 | Toàn bộ `fake_profile_post`; giữ lại để nghiên cứu riêng, cấm dùng trong benchmark V2. |
| `quarantine` | 3 | Một component phishing có nhãn nguồn mâu thuẫn; giữ nguyên nhãn, cấm train/evaluate. |

Tổng vẫn là 16.202 dòng. Ba tập benchmark, auxiliary và quarantine rời nhau và hợp lại đúng toàn bộ raw.

## Vì sao `fake_profile_post` được tách riêng

10.607 dòng `fake_profile_post` thuộc 1.387 account UUID. Mỗi account có nhiều post, trong khi các template văn bản còn nối nhiều account thành những component rất lớn. Nếu cố cân bằng 70/15/15 mà vẫn giữ cả account và template nguyên khối, split không còn đủ độc lập hoặc không còn đủ mẫu evaluation.

Vì vậy V2 giữ tất cả các dòng này ở `auxiliary` với lý do máy đọc được:

```text
entity_template_graph_not_splittable_without_leakage
```

Builder kiểm tra đủ 10.607 record ID, 1.387 UUID, cặp `(entity, post_index)` duy nhất, metadata account nhất quán và không có entity vượt partition. Hai cột `entity_group_id` và `entity_post_index` được thêm vào bản derived để phục vụ nghiên cứu nguồn này sau này.

## Quarantine nhãn mâu thuẫn

Ba record sau có cùng component văn bản nhưng nhãn nguồn là `1, 1, 0`:

- `phishing_5164`
- `phishing_5168`
- `phishing_14168`

Builder phát hiện mâu thuẫn bằng quy tắc, không dùng danh sách ID để quyết định. Cả component được chuyển sang `quarantine` với lý do:

```text
conflicting_labels_within_duplicate_template_group
```

Không có thao tác tự sửa hoặc bỏ nhãn. Danh sách ID chỉ được verifier dùng như invariant của raw đã pin.

## Cách tạo component văn bản

DSU/transitive closure hợp nhất record khi ít nhất một trong bốn khóa sau giống nhau:

1. `surface_normalized`, từ một token: NFKC, case-fold, bỏ dấu câu/whitespace khác biệt.
2. `legacy_template`, từ 10 token: thêm masking URL, email, handle và số theo normalizer V1.
3. `near_template_v2`, mọi khóa không rỗng: NFKC/lowercase, masking URL/email/handle/placeholder, thay từng chuỗi chữ số bằng `0`, chuẩn hóa whitespace nhưng giữ dấu câu/emoji.
4. `template_v2`, từ 10 token: masking typed placeholder và cả số nằm trong chuỗi như `5x`, `1000x`, `$25K`.

Khóa rỗng luôn bị bỏ qua, nên các text rỗng không bị gom vào một component giả. ID component ổn định là `GRP2_` cộng 16 ký tự hex đầu của SHA-256 trên danh sách `record_id` đã sắp xếp.

Kết quả có 5.762 component trên toàn bộ dữ liệu. Phần benchmark có 5.399 component, component lớn nhất 12 dòng. Không component nào và không khóa nào trong bốn normalizer vượt qua các partition mới.

## Chia benchmark

Sau khi tách auxiliary và quarantine, 5.592 dòng thuộc bốn nguồn `cresci_stock_2018`, `phishing`, `spam_email` và `twitter_bot_detection` được chia bằng greedy xác định:

- component lớn hơn được xử lý trước;
- mục tiêu đồng thời là tỷ lệ tổng và tỷ lệ trong từng `(source_dataset, source label)`;
- SHA-256 của membership là tie-break, không dùng raw/V1 partition và không dùng thứ tự dòng để quyết định mapping.

Tỷ lệ thực là 70,028612% train và 14,985694% cho mỗi evaluation partition. Sai lệch lớn nhất theo source-label là 0,165746 điểm phần trăm. Mỗi source-label stratum có tối thiểu 45 dòng và 45 component ở cả validation/test.

## Audit độc lập

Verifier dựng lại component từ raw và CSV derived, thay vì tin report của builder. Các kiểm tra đã đạt:

- raw SHA-256 trước/sau vẫn là `a4b336074176efb5746d1981506c1f1faba19a1b0a20f3b9e95dc8be94ea2504`;
- đủ 16.202 ID duy nhất, đúng thứ tự và giá trị của 32 cột raw;
- chỉ `partition` thay đổi và `original_partition` giữ đúng giá trị nguồn;
- zero component/normalized key vượt partition;
- đúng 10.607 auxiliary, 3 quarantine và `3.916/838/838` benchmark;
- không đổi nhãn, không gọi mạng và chưa train model.

Audit residual dùng `char_wb` TF-IDF 3–5 gram fit **chỉ trên train**. Kết quả vẫn có 43 validation và 31 test row với nearest-train cosine ≥ 0,95; tương ứng 11 và 5 row ≥ 0,99. Phần lớn tập trung ở spam/phishing. Đây là cảnh báo chẩn đoán: V2 kiểm soát các template đã biết, nhưng không chứng minh mọi semantic near-duplicate đã biến mất.

## Artifact và tái lập

Artifact chính nằm ngoài Git tại:

```text
D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\group_split_v2\
```

Gồm:

- `mendeley_v2_group_split_v2.csv`
- `split_report_v2.json`
- `split_audit_v2.json`

Registry đóng băng: `registry/splits/mendeley_group_split_v2.json`.

Tạo lại split từ raw đã pin:

```powershell
.venv\Scripts\python.exe scripts\build_mendeley_group_split_v2.py `
  --input <raw-v2.csv> `
  --output <output-dir>\mendeley_v2_group_split_v2.csv `
  --report <output-dir>\split_report_v2.json `
  --run-at 2026-09-15T14:40:00+00:00
```

Chạy audit:

```powershell
.venv\Scripts\python.exe scripts\audit_mendeley_group_split_v2.py `
  --input <output-dir>\mendeley_v2_group_split_v2.csv `
  --output <output-dir>\split_audit_v2.json `
  --run-at 2026-09-15T14:42:00+00:00
```

Kiểm tra registry và artifact local:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_group_split_v2_registry.py
```

Các lệnh mặc định từ chối ghi đè. Chỉ dùng `--overwrite` khi chủ động thay thế một artifact đã xác định.

## Bước tiếp theo

Train một baseline text mới từ đầu bằng **chỉ** ba partition benchmark V2. Không được dùng model hoặc metrics V1 làm kết quả V2; V1 được giữ lại như lịch sử thí nghiệm. Model mới phải chọn hoàn toàn trên validation trước khi mở test V2.
