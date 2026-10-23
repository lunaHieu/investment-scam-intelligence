# Project state and gap ledger V27

V27 thay V26 sau khi owner phê duyệt ngoại lệ thời gian A1.

- Ngoại lệ chỉ áp dụng cho `not_before`, từ 23:35 xuống 21:30 ngày 23/10/2026.
- Release V1 không bị sửa và QA override độc lập đã PASS.
- A1 vẫn giới hạn một request metadata, pacing 60 giây, stop-429, no-overwrite, không tải trang và không truy cập live domain.
- Tại snapshot này execution chưa chạy; C2/C3 preflight và mọi data/model gate giữ nguyên.
