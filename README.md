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
2. Mendeley V2 đã được ingest, audit leakage và chia lại theo duplicate/template group.
3. Text Baseline V1 đã đóng băng: Naive Bayes làm đối chứng; TF-IDF + Logistic Regression là baseline nội bộ chính.
4. Crimson pinned raw đã được chuẩn hóa thành URL candidates và lexical feature set không nhãn, hoàn toàn offline.
5. DFPI và SEC đang hoãn để tải thủ công hợp lệ; xem `docs/curated-evidence-pilot.md`.

Tiếp theo: profiling/clustering URL không nhãn để tạo review queue, sau đó chỉ train URL classifier khi có lớp đối chứng độc lập và external evidence-backed evaluation.

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

Audit phát hiện split gốc có lượng lớn nội dung trùng giữa train và evaluation. `scripts/build_mendeley_group_split.py` tạo split 70/15/15 mới, giữ duplicate/template candidates trong cùng một partition. Registry đóng băng nằm tại `registry/models/text_baseline_v1.json`.

Hai baseline chỉ dùng `text_content`:

- Multinomial Naive Bayes: baseline tối giản để tái lập.
- TF-IDF + Logistic Regression: baseline nội bộ chính; tham số chọn bằng validation, không dùng test.

Kết quả vẫn là benchmark label của Mendeley, không phải kết luận scam đã xác minh. Xem `docs/mendeley-text-model-comparison.md` và `docs/mendeley-prediction-error-comparison.md`.

Sau khi train, thử một văn bản (không gửi dữ liệu cá nhân) bằng:

```powershell
python scripts/predict_mendeley_text_baseline.py --model <model.json> --text "Guaranteed profit with no risk"
```

Kiểm tra hash, runtime và các điều kiện đóng băng:

```powershell
.venv\Scripts\python.exe scripts\verify_frozen_model.py --registry registry\models\text_baseline_v1.json
```

### Crimson URL lexical features

`scripts/extract_crimson_url_features.py` trích xuất feature từ chuỗi domain mà không gọi DNS, HTTP, WHOIS hoặc mở website. Output không có label và chưa được phép dùng để train binary classifier. Xem `docs/crimson-url-feature-readiness.md` và `registry/features/crimson_url_lexical_v1.json`.

Kiểm tra bằng:

```powershell
python scripts/validate_crimson_url_features.py --input <url-lexical-features.jsonl>
```

Kiểm tra contract của tệp candidate mà không mở URL:

```powershell
python scripts/validate_candidate_artifacts.py --input <candidate-artifacts.jsonl> --source-id crimson_www_2025
```

Trên máy triển khai hiện tại, raw data được lưu ngoài repository tại `D:\nckh 2026-2027\ISI_Data`. Khi ingest nguồn tiếp theo, chỉ định kho này rõ ràng, ví dụ: `--raw-root 'D:\nckh 2026-2027\ISI_Data\raw'`. Raw data không được commit vào GitHub.
