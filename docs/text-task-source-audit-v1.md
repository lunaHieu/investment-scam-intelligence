# Text task and source-role audit V1

## Kết luận

Điểm nghẽn hiện tại nằm ở **định nghĩa bài toán và sự tương thích của nhãn**, không chỉ ở năng lực encoder.

Mendeley V2 đã hợp nhất năm nhóm nguồn—phishing, spam email, fake-profile posts, Twitter bot detection và nội dung mạng xã hội liên quan tài chính—vào một binary schema rồi lọc theo mức liên quan đến đầu tư. Chính trang phát hành cũng giới hạn ý nghĩa nhãn ở deceptive/suspicious behaviour và không coi đó là verified investment-scam ground truth cho từng record: [Mendeley Data V2](https://data.mendeley.com/datasets/6wnd7jrt6z/2).

Vì vậy, `label=1` trong các nguồn không luôn trả lời cùng một câu hỏi:

- phishing: dấu hiệu phishing/message abuse;
- spam email: spam hoặc nội dung không mong muốn;
- Twitter bot: account automation/bot status;
- fake profile: profile authenticity;
- Cresci/finance social: deceptive hoặc automated behaviour trong ngữ cảnh tài chính.

Lọc một record theo chủ đề đầu tư không biến các nhãn nguồn này thành bằng chứng rằng record đó là một vụ lừa đảo đầu tư đã xác minh.

## Bằng chứng định lượng đã có

Không có model mới được chạy trong audit này. Tất cả con số đến từ các registry đã đóng băng:

| Bằng chứng | Kết quả | Ý nghĩa |
|---|---:|---|
| Text Baseline V2 internal test Macro-F1 | 0,706203 | Có signal nội bộ nhưng chưa đủ deployment |
| Twitter test Macro-F1 | 0,476064 | Text-only gần mức ngẫu nhiên trên nguồn bot |
| Lỗi baseline thuộc Twitter | 208/246, tương đương 84,5528% | Phần lớn lỗi nằm ở task bot/account |
| Lỗi ngắn ≤12 token | 192/246 | Nhiều đầu vào quá ngắn để suy ra hành vi tài khoản |
| Metadata missingness nhận diện source | 93,4541% accuracy | Cấu trúc dữ liệu tự tiết lộ nguồn |
| Source-majority label accuracy | 76,0395% | Nhãn và nguồn liên hệ mạnh |
| E5 source-predictability Macro-F1 | 0,932908 | Semantic embedding tiếp tục giữ dấu ấn nguồn |
| E5 nearest neighbor cùng nguồn | 94,5097% | Hình học embedding bị source/style chi phối mạnh |
| Wayback V2 nearest fit từ spam | 31/38 | Transfer vào website bị hút về style spam |
| Wayback V3 nearest fit từ spam | 19/30 | Mẫu source/style lặp lại trên holdout mới |

Ba hướng thay representation đã không khắc phục được vấn đề:

- Character V2: bị loại trên validation gate.
- Stop-word V3: bị loại trên development và validation gates.
- Frozen E5 V4: bị loại ngay trên OOF train; không mở validation/test/external.

Điều này không chứng minh mọi model khác sẽ thất bại. Nó cho thấy đổi representation trong khi giữ nguyên target hỗn hợp không phải bước tiếp theo có cơ sở nhất.

## Vai trò đề xuất cho từng nguồn

| Nguồn/nhóm | Vai trò hiện tại | Vai trò cho hệ thống cuối |
|---|---|---|
| `cresci_stock_2018` | Giữ trong `group_split_v2` lịch sử | Related-content auxiliary research; không phải scam ground truth |
| `phishing` | Giữ trong benchmark lịch sử | Related message-abuse auxiliary research |
| `spam_email` | Giữ trong benchmark lịch sử | Related unsolicited-content auxiliary research |
| `twitter_bot_detection` | Giữ nguyên benchmark để bảo toàn tính tái lập | Chuyển thành account/behavior auxiliary task trong thiết kế tương lai |
| `fake_profile_post` | Tiếp tục ở auxiliary | Account/profile-authenticity auxiliary task |
| Ba dòng phishing xung đột | Tiếp tục quarantine | Không train, không score |

“Giữ trong benchmark lịch sử” có nghĩa là không viết lại kết quả V2 và không âm thầm xóa nguồn để làm metric đẹp hơn. “Auxiliary task” có nghĩa là nguồn có thể hữu ích cho nghiên cứu phụ hoặc representation pretext sau một protocol riêng; nó không được tự động trở thành nhãn mục tiêu cuối.

## Định nghĩa mục tiêu nên dùng cho giai đoạn tiếp theo

Mục tiêu chính được đề xuất:

> Đánh giá rủi ro của solicitation/message/website liên quan đầu tư bằng evidence ở cấp case, với trạng thái `CONFIRMED`, `LEGITIMATE` hoặc `UNCERTAIN` được provenance và review hỗ trợ.

Hệ thống có thể có các đầu ra phụ riêng:

- content-risk classifier;
- URL/domain evidence score;
- financial-claim signals;
- account/bot-behaviour score khi thật sự có metadata hành vi;
- explanation layer tổng hợp bằng chứng.

Không nên ép tất cả các đầu ra này vào một binary label duy nhất chỉ vì chúng cùng có liên quan tới deception.

## Tác động đến dữ liệu và model hiện có

- `group_split_v2` không bị thay đổi và vẫn là benchmark lịch sử tái lập được.
- Text Baseline V2 vẫn là historical reference, không phải production candidate.
- Không có dòng nào bị relabel hoặc loại khỏi corpus hiện tại.
- Các external cohort V1/V2/V3 đã mở không được chuyển thành tuning/training data.
- Không có model, encoder, chunking hay hyperparameter mới được phép từ audit này.
- Không mở lại validation hoặc internal test.

## Bước bắt buộc tiếp theo

Trước lần train tiếp theo phải có một protocol mới cho **target-task và corpus construction**. Protocol đó cần đóng băng:

1. đơn vị ground truth là case hay artifact;
2. định nghĩa `CONFIRMED`, `LEGITIMATE`, `UNCERTAIN`;
3. nguồn nào được vào development training và nguồn nào chỉ là auxiliary/reference;
4. cách giữ campaign/domain/entity group không xuyên partition;
5. một external cohort mới, chưa từng score, dành cho đánh giá cuối;
6. điều kiện tối thiểu về số lượng và cân bằng trước khi cho phép model training.

Cho đến khi artifact này tồn tại, ưu tiên là xây target-aligned data chứ không chọn AI Agent hoặc model mạnh hơn.

