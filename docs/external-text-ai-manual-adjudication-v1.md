# External-text AI manual adjudication V1

## Mục tiêu

Vòng này ghi lại review thủ công do AI thực hiện cho toàn bộ 21 case đã có trong reviewer workbook: 10 case nhánh `CONFIRMED` và 11 case nhánh `LEGITIMATE`.

Kết quả AI được lưu thành lớp quyết định riêng. Nó không sửa raw/curated intake, không tự nhận là review của con người, không tạo nhãn và không mở external evaluation.

## Phương pháp

Với nhánh `CONFIRMED`, AI đọc snapshot ứng viên đã lưu, kiểm tra hash/host/danh tính/thời gian, rồi đối chiếu tên hoặc domain với trang cảnh báo chính thức của cơ quan quản lý. Domain ứng viên đang hoạt động không được mở trực tiếp.

Với nhánh `LEGITIMATE`, AI đọc capture đã lưu và hồ sơ SEC/IAPD đóng băng, kiểm tra CRD, trạng thái Registered/APPROVED, exact filed host, tên doanh nghiệp, contact alignment, nội dung trang, dấu hiệu parking/chiếm quyền/giả mạo và xử lý từng caution flag. SEC registration chỉ được dùng làm bằng chứng danh tính, không phải bảo chứng an toàn.

## Kết quả

- 21/21 AI review hoàn tất.
- 10/10 đề xuất `CONFIRMED`, confidence `HIGH` trong phạm vi bằng chứng.
- 11/11 đề xuất `LEGITIMATE`, confidence `HIGH` trong phạm vi bằng chứng.
- 0 hard contradiction còn mở.
- 0 human confirmation, 0 label, 0 external-evaluation eligibility.

Năm legitimate case có contact match thấp hoặc text ngắn đã được đọc riêng. Nội dung vẫn nhất quán với exact SEC-filed host và tên doanh nghiệp, không có dấu hiệu parking hoặc nội dung không liên quan trong capture. Tuy vậy, capture tĩnh không thể chứng minh tuyệt đối quyền kiểm soát máy chủ ở mọi thời điểm; giới hạn này được giữ trong từng record.

## Cổng tiếp theo

Artifact này làm cho 21 case `ready_for_human_adoption`, không phải `ready_for_reconciled_intake`. Cần một hành động chấp nhận riêng của người chịu trách nhiệm dữ liệu trước khi materialize nhãn. Nội dung cảnh báo của regulator tiếp tục bị tách khỏi model input.

