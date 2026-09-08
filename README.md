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

## Thứ tự triển khai tiếp theo

1. Rà lại registry và điều khoản/license của 3–5 nguồn Core trước khi ingest.
2. Viết adapter ingest riêng từng nguồn, lưu bản raw bất biến cùng manifest/timestamp/checksum.
3. Chuẩn hóa sang `ARTIFACTS`, deduplicate và tạo candidate `CASES`.
4. Chạy curated pilot + review guideline trước khi mở rộng quy mô.
5. Chạy TF-IDF baseline khi có vài nghìn mẫu curated hợp lệ.

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

Trên máy triển khai hiện tại, raw data được lưu ngoài repository tại `D:\nckh 2026-2027\ISI_Data`. Khi ingest nguồn tiếp theo, chỉ định kho này rõ ràng, ví dụ: `--raw-root 'D:\nckh 2026-2027\ISI_Data\raw'`. Raw data không được commit vào GitHub.
