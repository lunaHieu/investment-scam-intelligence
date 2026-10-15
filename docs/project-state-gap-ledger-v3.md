# Project state and remaining gates V3

## Tên bước và ý nghĩa

**P1R: refresh ledger sau các nhánh song song.** Ledger V3 thay thế ảnh chụp
trạng thái V2 cho việc lập kế hoạch hiện tại. Nó không thay đổi artifact lịch
sử, chỉ khóa bằng hash trạng thái sau khi P6 và P3T hoàn tất.

## Các nhánh đã hoàn tất

| Nhánh | Trạng thái | Ý nghĩa thực tế |
|---|---|---|
| P2 Raw QA | Hoàn tất | 278/278 file có chuỗi SHA-256 rooted từ Git; 0 mismatch |
| P3 External 21 | Hoàn tất ở mức diagnostic | 10 CONFIRMED + 11 LEGITIMATE; verifier V2 hoạt động; chưa phải human double-reviewed Gold |
| P6 Manual packet | Hoàn tất phần chuẩn bị | Có schema, template, hash/file validator; chưa tải file và chưa mở SSC/HNX |
| P7 Model dossier | Hoàn tất tài liệu | Giữ TF-IDF + logistic làm internal reference; không model mới được phép |
| P8 Reproducibility | Hoàn tất guide hiện tại | Luồng evidence, hash, review và gate đã được ghi nhận |

## Các nhánh chưa thể tự đóng bằng công việc offline

1. **P5 SEC/IAPD V4:** heartbeat chỉ được chạy từ
   `2026-10-16T00:48:55.969405+07:00`. Chỉ khi availability QA hoàn toàn pass
   mới được chuẩn bị capture plan.
2. **P4 Crimson:** còn 39 first review, 21 second review và 16 live-source gap.
   AI first pass đã đủ 40 nhưng không được tự xưng là human review.
3. **Nguồn thủ công:** DFPI cần artifact first-party hợp lệ; SSC/HNX cần export
   hoặc cơ sở reuse/permission được kiểm tra trước. Intake pass vẫn chưa tạo
   candidate hay label.

## Kết luận vận hành

Các việc chuẩn bị offline độc lập trong kế hoạch P2–P8 đã được thực hiện đến
gate hiện tại. Sự kiện tự động kế tiếp là heartbeat SEC/IAPD V4. Việc chủ dự án
có thể làm song song, nhưng không bắt buộc ngay, là cung cấp artifact/quyền sử
dụng theo P6 hoặc bố trí reviewer độc lập cho Crimson.

Không được dùng khoảng chờ để tự tạo quota fillers, mở live candidate domains,
thử model mới, mở validation/test, hoặc nâng diagnostic review thành Gold.
