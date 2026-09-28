# External-text reconciled pilot V1

## Kết quả gate

Ngày 2026-09-24, 21 draft external-text đã được materialize thành một batch riêng sau AI manual adjudication và lệnh tiếp tục của project owner:

- 10 `CONFIRMED`;
- 11 `LEGITIMATE`;
- 21 `HIGH + RECONCILED`;
- 21/21 raw capture hash hợp lệ;
- 21/21 exact text hash hợp lệ;
- 21/21 có strong evidence đã review;
- `reporting_allowed = true` với ngưỡng yêu cầu 10+10.

Các source draft vẫn được giữ nguyên `UNCERTAIN + LOW + IN_REVIEW`; chỉ batch reconciled mới chứa trạng thái được chấp nhận. Raw HTML không bị sửa.

## Provenance của review

AI đã đọc artifact và evidence, xử lý caution và đề xuất quyết định. Project owner cho phép tiếp tục sau khi nhận báo cáo tổng hợp. Artifact ghi rõ `independent_human_evidence_rereview = false`; không tuyên bố project owner đã tự mở và đọc lại độc lập từng bằng chứng.

## Hạn chế

Batch này đủ policy tối thiểu để chạy diagnostic external pilot, nhưng chưa phải Gold benchmark có double review. Hai nhánh thu thập cũng gần như trùng với hai lớp, nên mọi metric phải được diễn giải thận trọng.

