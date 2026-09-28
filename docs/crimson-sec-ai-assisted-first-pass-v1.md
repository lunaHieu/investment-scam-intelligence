# Crimson SEC AI-assisted first pass V1

## Kết quả

Toàn bộ 8 SEC/IAPD match trong pilot 40 host đã được kiểm tra theo từng hồ sơ.
Mỗi host Crimson đều trùng hoặc là subdomain của host được liệt kê trực tiếp trong
snapshot SEC/IAPD. First pass vì vậy đề xuất `SAME_ENTITY` và
`REGISTRATION_RELEVANT` cho cả 8 trường hợp.

Trong số 8 hồ sơ, 6 hồ sơ có loại `Registered` và trạng thái `APPROVED`; 2 hồ sơ
(`Hartmann Capital` và `Sango Capital Management`) là `ERA` với trạng thái
`ACTIVE`. ERA là exempt reporting adviser, không nên mô tả là adviser đã đăng ký
với SEC.

## Kiểm soát

- Không truy cập trực tiếp bất kỳ domain Crimson nào.
- First pass chỉ dùng snapshot SEC/IAPD đã khóa hash và URL hồ sơ SEC chính thức.
- `SAME_ENTITY` chỉ là kết luận sơ bộ về quan hệ danh tính/domain, không phải nhãn
  hợp pháp, an toàn hay scam.
- Cả 8 dòng giữ `review_status = IN_PROGRESS`, `training_eligible = NO` và
  `label_created = false` cho đến khi có xác nhận của người review.

Workbook đã được bổ sung tên thực thể, loại/trạng thái đăng ký, ngày filing, URL
SEC và rationale. Người review chỉ cần kiểm tra từng dòng SEC rồi đổi trạng thái
sang `COMPLETED` nếu đồng ý; không cần mở website Crimson.
