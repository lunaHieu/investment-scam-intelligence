# External text legitimate capture pilot V1

## Kết quả

Đã thử năm host được SEC/IAPD ghi nhận trong capture candidate queue. Ba host
không tạo raw artifact do lỗi TLS, timeout hoặc HTTP 403. Hai host tạo được HTML
capture bất biến:

- `EXTCAP_LEGIT_004`: Greenlea Lane Capital Management LLC, CRD 162012.
- `EXTCAP_LEGIT_005`: Paragon Financial Services, CRD 164832.

Đợt tiếp theo thử `EXTCAP_LEGIT_006` đến `015` nhưng cả 10 request cùng thất
bại tại DNS resolution. Do lỗi đồng nhất ở tầng môi trường, chúng được ghi là
`RETRYABLE_ENVIRONMENT_FAILURE`, không bị coi là website chết và không bị loại
khỏi queue. Báo cáo nguyên trạng được khóa hash trong pilot registry.

Feed SEC/IAPD ghi đúng business/legal name và đúng website cho cả hai firm.
Capture Paragon còn hiển thị địa chỉ và số điện thoại trùng với feed. Đây là
bằng chứng mạnh cho bước identity review, nhưng chưa tự động chứng minh mọi nội
dung, offer hoặc người đại diện là hợp pháp.

## Chuẩn hóa

Raw HTML không bị sửa. Derived text được tạo offline bằng `HTMLParser`:

- bỏ `script`, `style`, `noscript`, `svg`, `template`;
- chuẩn hóa whitespace;
- loại text node dài từ 40 ký tự trở lên nếu lặp chính xác do desktop/mobile
  responsive block;
- giữ canonical URL chỉ khi host chính xác hoặc biến thể `www` của candidate.

Kết quả text:

- Greenlea Lane: 332 ký tự, full identity-token match.
- Paragon: 5.307 ký tự sau dedup, full identity-token match.

## Trạng thái gate

Validator xác nhận cả hai capture tồn tại và SHA-256 khớp, không có structural
error. Tuy vậy cả hai vẫn là `UNCERTAIN + LOW + IN_REVIEW`, evidence chưa được
human-review và không có `LEGITIMACY` support đã reconcile. Vì thế:

- captured: 2;
- eligible legitimate: 0;
- eligible confirmed: 0;
- reporting allowed: `false`;
- model scoring/training: chưa được phép.

Hai raw capture nằm tại:

`D:\nckh 2026-2027\ISI_Data\raw\external_text_captures\2026-09-24\legitimate\`

Intake V2 và validation report nằm tại:

`D:\nckh 2026-2027\ISI_Data\derived\external_text_intake_v1\legitimate_capture_pilot_v1\`

Chạy verifier:

```powershell
.venv\Scripts\python.exe scripts\verify_external_text_legitimate_capture_pilot.py `
  --registry registry\pilots\external_text_legitimate_capture_pilot_v1.json
```

## AI-assisted first pass

Đối chiếu offline trực tiếp với SEC feed đưa ra hai khuyến nghị để con người
xem xét:

- `CASE_LEGIT_004`: `SAME_ENTITY_LIKELY`, đề xuất `LEGITIMATE`, confidence
  `MEDIUM_HIGH`. Host, registered/approved status và toàn bộ token tên firm khớp;
  số điện thoại duy nhất trong SEC feed không xuất hiện ở landing page.
- `CASE_LEGIT_005`: `SAME_ENTITY_LIKELY`, đề xuất `LEGITIMATE`, confidence
  `HIGH`. Ngoài host, status và tên, cả street, city, postal code, phone và fax
  trong capture đều khớp SEC feed.

Đây không phải hai nhãn. Intake vẫn giữ nguyên `UNCERTAIN + LOW + IN_REVIEW`,
human confirmation bằng 0 và external eligible bằng 0. Hai review brief nằm
trong thư mục `review_briefs_v2` dưới derived pilot folder.
