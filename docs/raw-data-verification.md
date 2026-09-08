# Kiểm tra độc lập raw data

Mục tiêu của tài liệu này là để một người khác có thể kiểm tra raw data mà **không cần tin vào người đã tải**. Raw không nằm trên GitHub; chỉ manifest, checksum và code kiểm tra được version control.

## Hai nguồn hiện có

| Source | File raw ở máy | Nguồn gốc có thể đối chiếu | Dấu vết bất biến |
| --- | --- | --- | --- |
| Mendeley V2 | `D:\nckh 2026-2027\ISI_Data\raw\mendeley_investment_deceptive_2026\v2\Multimodal_Dataset_for_Investment-Related_Deceptive_Content_Detection_on_Social_Platforms.csv` | DOI/dataset page: https://data.mendeley.com/datasets/6wnd7jrt6z/2 | Version `2`, SHA-256 trong `registry/manifests/mendeley_investment_deceptive_2026__v2__2026-09-07.json` |
| Crimson WWW 2025 | `D:\nckh 2026-2027\ISI_Data\raw\crimson_www_2025\b040e2def08ea26058ef9da752b72fa4a5238987\data.json` | `https://raw.githubusercontent.com/pragseclab/Crimson/b040e2def08ea26058ef9da752b72fa4a5238987/data/data.json` | Commit `b040e2def08ea26058ef9da752b72fa4a5238987`, SHA-256 trong `registry/manifests/crimson_www_2025__b040e2def08e__2026-09-08.json` |

## Cách tự kiểm tra

Chạy tại thư mục repository:

```powershell
python scripts/verify_raw_data.py
```

Lệnh chỉ đọc local raw data: nó không tải thêm gì và không truy cập URL scam. Kết quả cần có `sha256_matches_manifest: true` cho mỗi nguồn.

Để kiểm tra bằng PowerShell, người review có thể tự tính hash và so sánh với manifest:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '<raw-file-path>'
```

## Phân vai kiểm tra đề xuất

1. **Reviewer nguồn:** mở trang Mendeley hoặc GitHub Crimson, đối chiếu version/commit, license và mục đích dataset.
2. **Reviewer dữ liệu:** chạy script trên, kiểm tra SHA-256, kích thước file, số record và cột/field.
3. **Reviewer phương pháp:** xác nhận Mendeley chỉ là benchmark label và Crimson chỉ là research candidate; hai nguồn không được tự động thành Gold hay ground truth pháp lý.

## Điều cần biết

- Hash xác nhận file local đúng với manifest, không tự chứng minh dữ liệu là "scam đã được kết án".
- Mendeley: 16.202 dòng, 32 cột; nhãn nguồn là deceptive/suspicious benchmark.
- Crimson: 43.572 record; dataset research về website scam crypto. Candidate URL đã chuẩn hóa nằm ở `ISI_Data/interim`, còn raw file không thay đổi.
- Không một URL trong Crimson được truy cập trong các bước ingest, profile, normalize hoặc verify.
