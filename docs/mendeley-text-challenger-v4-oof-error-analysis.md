# Mendeley Text Challenger V4 — train-only OOF error analysis

## Kết luận chính

E5 thất bại ở development gate không phải vì một nhóm lỗi đơn lẻ. Bằng chứng hiện có phù hợp nhất với ba hạn chế kết hợp:

1. **Biểu diễn E5 mang dấu ấn nguồn/phong cách rất mạnh, trong khi nhãn bên trong từng nguồn bị lệch.** Láng giềng gần nhất trong không gian E5 cùng nguồn ở 94,5097% số dòng. Đồng thời, E5 luôn kém hơn ở nhãn thiểu số của từng nguồn và tốt hơn hoặc gần ngang ở nhãn đa số. Đây là mẫu phù hợp với việc bộ phân loại dựa quá nhiều vào nguồn/phong cách rồi nghiêng về nhãn phổ biến của nguồn đó.
2. **Giới hạn 512 token có liên hệ với suy giảm tương đối, nhưng không phải lời giải thích duy nhất.** Trong `spam_email`, net regression tăng từ 3,6320% ở dòng không bị cắt lên 10,9890% ở dòng bị cắt. Tuy vậy, độ dài và trạng thái cắt bị trộn lẫn với nguồn và loại tài liệu, nên không được diễn giải thành quan hệ nhân quả.
3. **Riêng `twitter_bot_detection`, nội dung văn bản ngắn không đủ tín hiệu ổn định cho bài toán nguồn.** Cả TF-IDF lẫn E5 đều gần mức ngẫu nhiên trên nguồn này. Mẫu review gồm nhiều câu ngắn hoặc chuỗi từ tổng hợp, trong khi nhãn bot có thể phụ thuộc vào hành vi/tài khoản mà đầu vào text-only không chứa.

Phân tích này chỉ giải thích cấu hình V4 đã bị loại. Nó không cấp phép thử encoder, prefix, pooling, chunking, `C`, threshold hoặc hyperparameter khác.

## Phạm vi và bảo vệ chống leakage

- Chỉ dùng 3.916 dòng `train`, thuộc 3.783 `split_group_id`.
- Chỉ đọc dự đoán OOF và embedding train đã tồn tại của cấu hình V4 đóng băng.
- Không tạo embedding mới, không chạy forward pass, không fit/refit và không score model.
- Không giữ lại text hay truy cập nhãn của validation/test; không dùng external, auxiliary hoặc quarantine.
- Không thay nhãn, không đổi training eligibility và không mở lại quyết định model.
- Protocol được khóa trước khi xem lỗi theo từng dòng: `configs/mendeley_text_challenger_v4_oof_error_analysis_protocol.json`.

## Chuyển trạng thái lỗi OOF

| Chuyển trạng thái | Số dòng |
|---|---:|
| Cả hai đúng | 2.258 |
| TF-IDF đúng, E5 sai — E5 regression | 567 |
| TF-IDF sai, E5 đúng — E5 recovery | 444 |
| Cả hai sai | 647 |

E5 tạo thêm ròng 123 lỗi: 567 regressions trừ 444 recoveries, tương đương net regression 3,1410 điểm phần trăm. Tỷ lệ lỗi tăng từ 27,8601% của TF-IDF lên 31,0010% của E5.

Theo nguồn:

| Nguồn | E5 regression | E5 recovery | Net regression rate |
|---|---:|---:|---:|
| `cresci_stock_2018` | 78 | 64 | 2,5688% |
| `phishing` | 40 | 17 | 3,1165% |
| `spam_email` | 65 | 10 | 7,0785% |
| `twitter_bot_detection` | 384 | 353 | 1,6703% |

`spam_email` là nơi E5 mất nhiều nhất theo tỷ lệ. `twitter_bot_detection` đóng góp số lỗi lớn nhất theo số lượng vì nguồn này chiếm 1.856/3.916 dòng và cả hai mô hình đều yếu.

## Mẫu nguồn–nhãn

| Nguồn | Nhãn | Số dòng | Net E5 regression rate |
|---|---:|---:|---:|
| `cresci_stock_2018` | 0 — thiểu số | 254 | +11,0236% |
| `cresci_stock_2018` | 1 — đa số | 291 | -4,8110% |
| `phishing` | 0 — thiểu số | 268 | +8,2090% |
| `phishing` | 1 — đa số | 470 | +0,2128% |
| `spam_email` | 0 — đa số | 566 | -0,1767% |
| `spam_email` | 1 — thiểu số | 211 | +26,5403% |
| `twitter_bot_detection` | 0 — thiểu số | 904 | +5,6416% |
| `twitter_bot_detection` | 1 — đa số | 952 | -2,1008% |

Mẫu này nhất quán ở cả bốn nguồn: nhãn thiểu số chịu suy giảm lớn hơn nhãn đa số. Trường hợp nghiêm trọng nhất là `spam_email|label=1`: 64 regressions, 8 recoveries, và tỷ lệ lỗi E5 32,7014% so với 6,1611% của TF-IDF.

Đây là bằng chứng mô tả phù hợp với **source/style shortcut cộng với lệch nhãn trong từng nguồn**. Nó chưa chứng minh cơ chế nhân quả của từng dự đoán và không chứng minh encoder tự thân luôn thiên lệch theo nguồn.

## Hình học láng giềng của embedding đã có

Láng giềng gần nhất được tính trong embedding E5 train đã chuẩn hóa L2, loại chính dòng đó và mọi dòng cùng `split_group_id`.

| Nhóm | Cùng nguồn | Cùng nhãn | Cùng nguồn và nhãn |
|---|---:|---:|---:|
| Tất cả | 94,5097% | 71,9356% | 67,9520% |
| Cả hai đúng | 93,6670% | 84,9867% | 79,6723% |
| E5 regression | 95,7672% | 60,4938% | 58,3774% |
| E5 recovery | 94,8198% | 52,7027% | 50,0000% |
| Cả hai sai | 96,1360% | 49,6136% | 47,7589% |

Không gian E5 gần như luôn giữ nguồn, nhưng độ nhất quán nhãn giảm mạnh ở các nhóm lỗi. Kết quả này bổ trợ cho diễn giải shortcut nguồn/phong cách; nó không cho biết đặc trưng cụ thể nào đã gây ra từng quyết định của logistic regression.

## Truncation và độ dài

Có 379 dòng vượt 512 token: 364 từ `spam_email`, 15 từ `phishing` và không có dòng nào từ hai nguồn Twitter.

| Nhóm độ dài trước cắt | Số dòng | E5 regression | E5 recovery | Net regression rate |
|---|---:|---:|---:|---:|
| ≤32 | 2.251 | 437 | 393 | 1,9547% |
| 33–128 | 741 | 54 | 41 | 1,7544% |
| 129–512 | 545 | 30 | 8 | 4,0367% |
| >512 | 379 | 46 | 2 | 11,6095% |

So sánh toàn cục “bị cắt với không bị cắt” dễ gây hiểu sai vì nhóm bị cắt gần như toàn email spam. So sánh bên trong nguồn vẫn cho thấy mối liên hệ đáng lưu ý:

- `spam_email`: net regression 3,6320% khi không bị cắt và 10,9890% khi bị cắt.
- `phishing`: 2,6279% khi không bị cắt và 26,6667% khi bị cắt, nhưng nhóm bị cắt chỉ có 15 dòng.

Vì vậy, truncation là **yếu tố phụ có liên hệ với suy giảm**, không đủ bằng chứng để gọi là nguyên nhân chính. Phân tích không thử chunking hoặc thay đổi giới hạn token.

## Review định tính có giới hạn

Queue gồm 60 dòng: tối đa 5 dòng cho mỗi tổ hợp nguồn × (`e5_regression`, `e5_recovery`, `both_wrong`), không lặp group trong từng tầng. Excerpt đã được redaction; review không thay nhãn.

Các mẫu quan sát được:

- Các regression `spam_email|label=1` nổi bật là email quảng bá cổ phiếu/đầu tư rất dài; cả 5 mẫu regression ưu tiên đều vượt 512 token. Điều này phù hợp với tương tác giữa dấu ấn nguồn, nhãn đa số và truncation, nhưng không tách được đóng góp nhân quả của từng yếu tố.
- Một số regression nhãn 0 ở `cresci_stock_2018` và `phishing` chứa từ ngữ mang nghĩa rủi ro hoặc quảng bá như crypto, thu nhập thụ động, “buy now”, ưu đãi và tính khẩn cấp. Encoder ngữ nghĩa có thể gom chúng gần nội dung nhãn 1 hơn, trong khi TF-IDF giữ được mẫu từ/cấu trúc theo corpus. Đây chỉ là giả thuyết phù hợp với ví dụ, không phải phép giải thích mô hình chính thức.
- Nhiều dòng Twitter là bio ngắn hoặc chuỗi từ giống văn bản tổng hợp. Nhãn nguồn có thể phản ánh bot/account behavior không quan sát được trong một câu text-only.
- Một số dòng `phishing|label=0` vẫn có vẻ đáng ngờ hoặc quảng bá khi chỉ đọc excerpt. Điều này nhắc rằng nhãn hiện tại là nhãn hài hòa theo corpus, không phải xác minh regulator cho từng record; review không được dùng để tự ý gọi đó là label noise.

## Điều đã biết và chưa biết

**Được hỗ trợ bởi dữ liệu:** E5 kém TF-IDF trên OOF train; suy giảm tập trung ở nhãn thiểu số theo nguồn; embedding giữ nguồn mạnh; truncation đi kèm suy giảm tương đối trong hai nguồn có văn bản dài; text-only rất yếu trên Twitter bot.

**Chưa được chứng minh:** encoder nào khác sẽ tốt hơn; chunking sẽ khắc phục lỗi; prefix/pooling là nguyên nhân; thay `C` hoặc threshold sẽ có lợi; bất kỳ dòng nào bị gán nhãn sai; kết quả sẽ lặp lại trên validation/test/external.

## Quyết định

- Giữ trạng thái V4: **rejected at development gate**.
- Validation, internal test và external benchmarks tiếp tục đóng đối với challenger này.
- Không dùng phân tích lỗi để âm thầm chọn model hoặc cấu hình mới.
- Nếu sau này muốn kiểm tra một giả thuyết mới, phải tạo protocol riêng, nêu đúng một thay đổi có căn cứ, đóng băng gate trước khi tính toán, và tiếp tục dùng development train-only trước khi xin mở validation.

