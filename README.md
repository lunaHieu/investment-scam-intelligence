# Investment Scam Intelligence

Repository khởi động cho **Investment Scam Intelligence (ISI) V1**: nghiên cứu và xây dựng hệ thống hỗ trợ phát hiện, đánh giá rủi ro và giải thích dấu hiệu lừa đảo đầu tư trong nội dung trực tuyến.

Mục tiêu của repository này là bảo vệ tính toàn vẹn dữ liệu và thí nghiệm trước khi xây mô hình. Hệ thống lấy `case` làm đơn vị ground truth, còn post, URL, ảnh và tài liệu cảnh báo là `artifact` hoặc `evidence` có provenance riêng.

## Phạm vi V1

- Core: Text, Image, URL và Financial Claims.
- Extension: metadata hành vi/tài khoản.
- Không phải: phán quyết pháp lý, khuyến nghị đầu tư, full phishing detector, truy vết blockchain hay custom large multimodal model.

## Nguyên tắc dữ liệu không được phá vỡ

1. Giữ nguyên `source_label` và ý nghĩa nhãn từ nguồn. Chỉ `thesis_label` sau review mới là nhãn dùng cho nghiên cứu.
2. Ground truth nằm ở `case`, không suy ra tự động cho mọi artifact cùng nguồn.
3. Không dùng bài cảnh báo của cơ quan quản lý làm positive solicitation sample mặc định.
4. Split theo case/campaign/entity/domain-family/near-duplicate group, không random từng hàng.
5. Các trường xác minh như `ground_truth_status`, `source_id`, `label_confidence` và `review_notes` bị cấm làm predictive feature.
6. Gold test chỉ dùng để đánh giá cuối; không tune threshold hay chọn model trên Gold.

## Bắt đầu

```powershell
python -m unittest discover -s tests -v
python scripts/validate_registry.py
```

Các lệnh chỉ kiểm tra contract hiện có; chưa tải dữ liệu, crawl hay gọi API nào.

## Cấu trúc

| Thư mục | Vai trò |
| --- | --- |
| `schemas/` | JSON Schema cho các thực thể dữ liệu cốt lõi. |
| `registry/` | Source registry, taxonomy, policy evidence và guideline gán nhãn. |
| `data/` | Raw, interim, clean, curated, gold và embeddings; chỉ giữ placeholder trong Git. |
| `src/isi/` | Code nghiệp vụ theo pipeline. |
| `scripts/` | Kiểm tra contract và công cụ vận hành. |
| `tests/` | Unit test không phụ thuộc dữ liệu bên ngoài. |
| `configs/` | Cấu hình split và experiment có thể thay đổi qua thực nghiệm. |

## Trạng thái hiện tại

1. Data contracts, source registry, evidence rules và split policy đã có validator.
2. Mendeley V2 đã có `group_split_v2` strict: 5.592 dòng benchmark bốn nguồn, 10.607 `fake_profile_post` ở auxiliary và 3 dòng nhãn mâu thuẫn ở quarantine; raw vẫn nguyên vẹn.
3. Text Baseline V2 đã được chọn hoàn toàn trên validation rồi mới mở test: word TF-IDF + Logistic Regression, test Macro-F1 0,7062; error analysis xác nhận 208/246 lỗi đến từ `twitter_bot_detection`. Baseline đã được score theo protocol trên nhiều external cohort đã reconcile nhưng vẫn không đủ điều kiện deployment.
4. Financial Claims đã hoàn tất các vòng review V1–V4 và ablation trên `group_split_v2`; text-only vẫn được giữ vì feature claims không qua promotion gate.
5. Metadata ablation trên Mendeley đã hoàn tất; metadata không được promote vì không cải thiện đồng thời internal test và leave-one-source-out, còn missingness nhận diện nguồn rất mạnh.
6. Source-balance ablation đã hoàn tất; validation vẫn chọn text baseline không trọng số, nên không thay baseline.
7. Text-representation ablation đã hoàn tất; `word + char_wb` tăng LOSO nhưng giảm internal test, đồng thời audit phát hiện source/template shortcut lớn, nên vẫn giữ word baseline.
8. Crimson pinned raw đã được chuẩn hóa thành URL candidates, lexical feature set, phân tích clustering/outlier không nhãn và các pilot đối chiếu reference, hoàn toàn tách khỏi Gold/training labels.
9. SEC IAPD và IOSCO đã có offline reference index; DFPI vẫn hoãn để lấy export hợp lệ. Image branch tiếp tục bị chặn vì chưa có image dataset có license, provenance và nhãn tương thích.
10. Ba text challenger mới đã bị loại có kiểm soát: character V2, stop-word V3 và frozen E5 V4. E5 thất bại ngay trên OOF `train`, nên validation/test/external không được mở cho challenger này.

Tiếp theo: giữ Text Baseline V2 làm reference nhưng không deploy. Trước khi train ứng viên mới, phải audit lại định nghĩa bài toán và vai trò từng nguồn—đặc biệt `twitter_bot_detection`—rồi đóng băng đúng một hypothesis mới. Mọi ứng viên tiếp theo phải bắt đầu bằng grouped OOF chỉ trên `train`; chỉ khi qua toàn bộ development gate mới được mở validation. Các external cohort đã score chỉ còn vai trò chẩn đoán, không được dùng để tune hoặc làm headline benchmark cho ứng viên mới.

### UBCKNN warning pilot

Pilot đầu tiên nằm tại `registry/pilots/ubcknn_warning_seed_2026-09-08.json`. Đây là **5 case/evidence từ cảnh báo công khai của UBCKNN**, dùng để thử nghiệm quy trình case-first và review; không phải tập post lừa đảo, không phải tập huấn luyện và không phải Gold test. Kiểm tra bằng:

```powershell
python scripts/validate_ubcknn_pilot.py
```

Chi tiết về điều kiện thu thập của các nguồn Core nằm tại [`registry/source_readiness.md`](registry/source_readiness.md). Không ingest dữ liệu trước khi có manifest đúng schema.

### Mendeley V2 ingestion

Sau khi tải thủ công CSV của đúng bản V2 từ Mendeley, chạy:

```powershell
python scripts/ingest_mendeley.py --input <downloaded-csv-path>
```

Adapter chỉ copy raw file bất biến, tạo SHA-256 manifest và profile cột; không đổi nhãn gốc, không upload dữ liệu và không tạo Gold data.

### Crimson ingestion

Chỉ dùng `data/data.json` từ một commit đã pin; không chạy bất kỳ crawler, login automation hoặc truy cập URL nào nằm trong dataset. Ví dụ:

```powershell
python scripts/ingest_crimson.py --input <data.json> --commit <40-character-commit-sha> --raw-root 'D:\nckh 2026-2027\ISI_Data\raw'
```

Adapter chỉ lưu tệp JSON bất biến, SHA-256 manifest và profile cấu trúc; dataset Crimson vẫn là nguồn research/Silver, không phải Gold thực tế.

Sau ingest, chuẩn hóa thành candidate URL artifact mà không truy cập bất kỳ URL nào trong dữ liệu:

```powershell
python scripts/normalize_crimson.py --input <pinned-data.json> --output <candidate-artifacts.jsonl> --report <report.json> --collection-date 2026-09-08
```

Các artifact này chưa có `case_id`, không được coi là Gold và phải được deduplicate theo domain/campaign trước khi tạo split hoặc dùng cho mô hình.

### Kiểm tra raw data độc lập

Raw data nằm ngoài GitHub để không đưa dữ liệu nguồn lên public. Một người khác có thể đối chiếu source version/commit, SHA-256 và cấu trúc dữ liệu bằng lệnh chỉ đọc:

```powershell
python scripts/verify_raw_data.py
```

Xem chi tiết tại [`docs/raw-data-verification.md`](docs/raw-data-verification.md).

### Mendeley text baseline

Audit phát hiện split gốc có lượng lớn nội dung trùng giữa train và evaluation. Baseline V1 và registry `registry/models/text_baseline_v1.json` dùng `group_split_v1`, vì vậy chỉ còn vai trò lịch sử và không phải kết quả của split strict mới.

`group_split_v2` giữ đủ 16.202 dòng nhưng chỉ 5.592 dòng từ bốn nguồn được phép vào benchmark; toàn bộ `fake_profile_post` nằm ở auxiliary và ba dòng nhãn mâu thuẫn nằm ở quarantine. Xem `docs/mendeley-group-split-v2.md` và registry `registry/splits/mendeley_group_split_v2.json`. Kiểm tra artifact local bằng:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_group_split_v2_registry.py
```

Text Baseline V2 dùng word TF-IDF unigram+bigram và Logistic Regression. Mười candidate được xếp hạng trên validation theo source-mean Macro-F1; selection `C=2.0`, không class weight được đóng băng và kiểm tra digest trước khi test được mở. Model cuối refit trên train+validation, không dùng 10.607 auxiliary hoặc 3 quarantine. Xem `docs/mendeley-text-baseline-v2.md` và registry `registry/models/text_baseline_v2.json`.

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_text_baseline_v2_registry.py
```

Error analysis V2 tái tạo đủ 838 dự đoán, ghi nhận 246 lỗi và tạo queue 44 group đại diện mà không fit lại model hoặc tạo nhãn mới. Xem `docs/mendeley-text-baseline-v2-error-analysis.md` và registry tại `registry/analyses/mendeley_text_baseline_v2_error_analysis.json`.

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_text_baseline_v2_error_analysis_registry.py
```

External-evaluation readiness audit ban đầu từng đóng gate vì chưa có observed text artifact đã reconcile. Sau đó pipeline đã tạo pilot 21 record, matched Wayback V1, Wayback language V2 và untouched holdout V3 với review độc lập trước khi score baseline cố định. Các cohort đã mở này chỉ dùng cho báo cáo và chẩn đoán, không được dùng để tune ứng viên tiếp theo. Audit lịch sử nằm tại `docs/text-baseline-v2-external-evaluation-readiness.md`; kết quả mới hơn nằm trong các tài liệu `docs/text-baseline-v2-*wayback*.md` và registry tương ứng dưới `registry/analyses/`.

```powershell
.venv\Scripts\python.exe scripts\verify_text_baseline_v2_external_readiness_registry.py
```

Hai baseline chỉ dùng `text_content`:

- Multinomial Naive Bayes: baseline tối giản để tái lập.
- TF-IDF + Logistic Regression: baseline nội bộ chính; tham số chọn bằng validation, không dùng test.

Kết quả vẫn là benchmark label của Mendeley, không phải kết luận scam đã xác minh. Xem `docs/mendeley-text-model-comparison.md` và `docs/mendeley-prediction-error-comparison.md`.

Lệnh dự đoán dưới đây chỉ áp dụng cho model V1 lịch sử. Sau khi train model V2 mới, phải dùng đúng registry/model artifact V2 tương ứng:

```powershell
python scripts/predict_mendeley_text_baseline.py --model <model.json> --text "Guaranteed profit with no risk"
```

Kiểm tra hash, runtime và các điều kiện đóng băng:

```powershell
.venv\Scripts\python.exe scripts\verify_frozen_model.py --registry registry\models\text_baseline_v1.json
```

### Mendeley metadata ablation

Chín biến thể tách text, metadata hành vi/tài khoản, thống kê nội dung và cờ thiếu dữ liệu đã được đánh giá trên cùng `group_split_v1`. Missingness đơn thuần nhận diện nguồn với 93,45% accuracy trên test; không biến thể text + metadata nào cải thiện đồng thời internal-test và leave-one-source-out Macro-F1. Vì vậy metadata chưa được đưa vào baseline chính.

Xem `docs/mendeley-metadata-ablation-v1.md` và registry đóng băng tại `registry/models/mendeley_metadata_ablation_v1.json`. Kiểm tra bằng:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_metadata_ablation_registry.py
```

### Mendeley source-balance ablation

Năm chiến lược trọng số train đã được so sánh trên cùng TF-IDF + Logistic Regression cố định. Inverse-source cải thiện leave-one-source-out nhưng làm giảm mạnh internal test; inverse-source-label chỉ tăng nhẹ test và không có ý nghĩa thống kê. Validation chọn lại mô hình không trọng số, vì vậy `ISI_TEXT_BASELINE_V1` vẫn được giữ nguyên.

Xem `docs/mendeley-source-balance-ablation-v1.md` và registry tại `registry/models/mendeley_source_balance_ablation_v1.json`. Kiểm tra bằng:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_source_balance_ablation_registry.py
```

### Mendeley text-representation ablation

Word TF-IDF, `char_wb`, raw `char` diagnostic và `word + char_wb` đã được so sánh với cùng Logistic Regression cố định. Validation chọn `word + char_wb` trong nhóm hợp lệ, nhưng biến thể này giảm internal-test Macro-F1, không cải thiện nguồn nào và không vượt paired group-bootstrap gate. Audit bổ sung còn phát hiện 193 normalized template vượt partition và character text nhận diện nguồn rất mạnh. Vì vậy `ISI_TEXT_BASELINE_V1` vẫn được giữ nguyên; mọi thử nghiệm normalization tiếp theo phải dựng lại split bằng cùng normalizer.

Xem `docs/mendeley-text-representation-ablation-v1.md` và registry tại `registry/models/mendeley_text_representation_ablation_v1.json`. Kiểm tra bằng:

```powershell
.venv\Scripts\python.exe scripts\verify_mendeley_text_representation_ablation_registry.py
```

### Crimson URL lexical features

`scripts/extract_crimson_url_features.py` trích xuất feature từ chuỗi domain mà không gọi DNS, HTTP, WHOIS hoặc mở website. Output không có label và chưa được phép dùng để train binary classifier. Xem `docs/crimson-url-feature-readiness.md` và `registry/features/crimson_url_lexical_v1.json`.

Kiểm tra bằng:

```powershell
python scripts/validate_crimson_url_features.py --input <url-lexical-features.jsonl>
```

Phân tích không nhãn dùng clustering/outlier để tạo review queue 100 domain,
không tạo nhãn và không truy cập website. Xem
`docs/crimson-domain-unsupervised-analysis.md` và
`registry/analyses/crimson_domain_unsupervised_v1.json`.

Kiểm tra contract của tệp candidate mà không mở URL:

```powershell
python scripts/validate_candidate_artifacts.py --input <candidate-artifacts.jsonl> --source-id crimson_www_2025
```

Trên máy triển khai hiện tại, raw data được lưu ngoài repository tại `D:\nckh 2026-2027\ISI_Data`. Khi ingest nguồn tiếp theo, chỉ định kho này rõ ràng, ví dụ: `--raw-root 'D:\nckh 2026-2027\ISI_Data\raw'`. Raw data không được commit vào GitHub.
