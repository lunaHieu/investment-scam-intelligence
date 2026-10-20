# Phương pháp và tiến độ nghiên cứu V1

Ngày chốt: 2026-10-20

## Mục tiêu đo lường

Đề tài xây dựng hệ thống phát hiện nội dung lừa đảo đầu tư từ dữ liệu đa nguồn.
Một kết quả có ý nghĩa phải trả lời đúng đối tượng cần phát hiện, tổng quát sang
nhóm/domain mới và có provenance đủ để kiểm tra lại. Vì vậy, nhiều file raw
hoặc nhiều URL chưa đồng nghĩa với nhiều mẫu train tốt.

## Năm tầng dữ liệu không được cộng lẫn

1. **Raw artifact:** byte gốc đã lưu và kiểm tra hash.
2. **Reference/candidate:** đầu mối hoặc bằng chứng để xem xét; chưa có nhãn.
3. **Reviewable artifact:** nội dung quan sát được đã extract, loại trùng và
   ghép nhóm; vẫn có thể `UNCERTAIN`.
4. **Admitted labeled group:** đã qua primary review, blind second review,
   reconciliation và owner acceptance.
5. **Model split:** nhóm đã admitted và được phân vào development hoặc external
   holdout theo hợp đồng disjoint.

Chỉ tầng 4 và 5 mới có thể đóng góp vào corpus mục tiêu. Bài cảnh báo, registry
membership, availability và complaint không tự trở thành nhãn.

## Quy trình hoàn chỉnh

`source permission -> immutable capture -> byte/hash QA -> exact text ->
opened-overlap exclusion -> transitive grouping -> primary review -> blind
second review -> reconciliation -> owner acceptance -> split freeze ->
development training -> validation selection -> one-time test`

Mọi bước sau phụ thuộc cổng trước. Validation và test không được dùng để thử ý
tưởng hoặc chọn hyperparameter.

## Phân công AI và con người

AI có thể tải theo release đã đóng băng, kiểm tra hash, extract offline, tìm
trùng, tạo packet, tóm tắt bằng chứng có trích nguồn, chạy kiểm thử và phát hiện
vi phạm hợp đồng. AI không được tạo danh tính reviewer giả, biến gợi ý thành
quyết định con người, suy nhãn từ availability/registry hay tự chấp nhận mẫu vào
corpus.

Con người chịu trách nhiệm về quyền truy cập/tái sử dụng khi nguồn yêu cầu,
đánh giá bằng chứng độc lập, xử lý bất đồng và owner acceptance. Blind second
review phải thật sự không nhìn thấy kết quả primary.

## Trạng thái đã kiểm chứng

| Trục tiến độ | Đã có | Chưa được hiểu thành |
|---|---:|---|
| Raw storage hiện hữu | 278 file đã kiểm tra toàn vẹn | 278 mẫu train |
| Baseline lịch sử | 3.916 dòng train, validation/test đóng | Fresh target corpus |
| Fresh V1-Core | 0/300 nhóm admitted | Thiếu model mạnh hơn |
| SEC/IAPD availability | 113/115 resolved | 113 nhãn hoặc artifact |
| SEC/IAPD capture plan | 58 dòng: 46 development, 12 external holdout | 58 dòng train |
| Crimson first review | 1/40 hoàn tất; 39 còn lại | 40 nhãn |
| Crimson blind second | 1 sẵn sàng, 20 đang chờ primary | Independent review hoàn tất |
| DFPI/SSC/HNX | 0 artifact đã intake | Kênh dữ liệu đã hoạt động |
| Vietnamese supply | 0 verified | Độ phủ ngôn ngữ Việt |
| Usable image assets | 0 | Multimodal model readiness |

Không dùng một phần trăm tổng duy nhất vì các mẫu số khác nhau. Hiện discovery
SEC/IAPD đạt 113/115 (98,26%), nhưng corpus mục tiêu vẫn 0/300 (0%). Hai con số
đo hai việc hoàn toàn khác nhau.

## Kết quả model hiện tại

Baseline word TF-IDF tuyến tính trên đúng 3.916 dòng train có OOF Macro-F1
0,721038. E5-small-v2 đạt 0,689907, giảm trên mọi nguồn và thất bại toàn bộ sáu
development gate. Character augmentation và style guard cũng không vượt gate.
Kết luận hiện tại không phải “cần model lớn hơn”, mà là dữ liệu còn bị chi phối
bởi source/style và fresh target corpus chưa tồn tại.

## Thứ tự tiếp theo

1. Tại gate thời gian, chạy V9 availability retry và capture V5 bất biến.
2. Kiểm tra độc lập byte/hash rồi exact-text và grouping.
3. Thực hiện group review, primary review, blind second review và reconciliation.
4. Song song, hoàn tất review Crimson và nhận artifact/quyền sử dụng hợp lệ cho
   DFPI/SSC/HNX.
5. Chỉ khi đủ coverage và 300 nhóm admitted mới đóng băng split/candidate model,
   dùng validation để chọn một cấu hình rồi mở test đúng một lần.

Theo cách này, phần chậm nhất của đề tài hiện là tạo bằng chứng và nhãn đáng tin,
không phải huấn luyện thuật toán.
