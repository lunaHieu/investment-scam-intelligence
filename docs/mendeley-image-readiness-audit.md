# Kiểm định mức sẵn sàng của nhánh ảnh — Mendeley V2

## Kết luận

Các tệp Mendeley V2 hiện có **không chứa dữ liệu ảnh có thể dùng để train mô
hình ảnh**. Nhánh ảnh được đặt trạng thái `BLOCKED_NO_IMAGE_ASSETS`.

Trong bộ dữ liệu này, “multimodal” nghĩa là kết hợp **text và metadata hành
vi/tài khoản**. Trang nguồn mô tả 20 trường behavioral metadata và hai nhóm
`text_plus_metadata`/`text_only`; không mô tả một tập ảnh đi kèm. Xem
[Mendeley Data V2](https://data.mendeley.com/datasets/6wnd7jrt6z/2).

## Những gì đã kiểm tra

| Kiểm tra | Kết quả |
| --- | ---: |
| CSV đúng số record | 16.202 |
| CSV đúng số cột | 32 |
| `text_plus_metadata` | 14.035 |
| `text_only` | 2.167 |
| Cột liên quan tới ảnh | Chỉ có `default_profile_image_flag` |
| Image path/URL/bytes trong cột liên quan ảnh | 0 |
| File ảnh trong thư mục raw | 0 |
| Media nhúng trong XLSX | 0 |
| External link entry trong XLSX | 0 |

SHA-256 của CSV là
`a4b336074176efb5746d1981506c1f1faba19a1b0a20f3b9e95dc8be94ea2504`,
khớp manifest đã khóa.

## Điểm dễ hiểu nhầm

`default_profile_image_flag` có 3.704 giá trị `1`, 7.680 giá trị `0` và 4.818
giá trị thiếu. Đây chỉ là cờ metadata cho biết tài khoản có dùng ảnh đại diện
mặc định hay không. Nó không chứa ảnh đại diện, đường dẫn ảnh, embedding hay
pixel; vì vậy không thể đưa vào CNN/ViT như dữ liệu ảnh.

Năm đoạn text có chuỗi giống phần mở rộng file ảnh. Chúng chỉ là ký tự trong
`text_content`, không có URL HTTP và không trỏ tới asset cục bộ, nên cũng không
được coi là ảnh.

## Quyết định phương pháp

- Không tạo image dataset từ Mendeley V2 hiện tại.
- Không đổi tên metadata thành image modality.
- Có thể dùng 14.035 record `text_plus_metadata` cho một thí nghiệm ablation
  text + behavior sau này; đây là nhánh extension, không thay thế nhánh ảnh.
- Muốn mở nhánh ảnh, cần một nguồn riêng có file ảnh hoặc snapshot, provenance,
  license và nhãn có ý nghĩa phù hợp với đề tài.
- Nhãn Mendeley vẫn chỉ là deceptive/suspicious benchmark, không phải xác minh
  scam thực tế cho từng record.

## Tái lập kiểm định

```powershell
python scripts\audit_mendeley_image_readiness.py `
  --csv <mendeley-v2.csv> `
  --xlsx <mendeley-v2.xlsx> `
  --output outputs\mendeley_image_readiness_v1\image_readiness_report.json

python scripts\verify_mendeley_image_readiness_registry.py `
  --registry registry\analyses\mendeley_image_readiness_v1.json
```
