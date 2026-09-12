# Phân tích lỗi baseline trên Mendeley group split V1

## Kết luận nhanh

Test có 2,429 mẫu và 256 lỗi: 101 false positives, 155 false negatives. Có 120 lỗi mà model tự tin từ 90% trở lên.

Các nhãn vẫn là benchmark deceptive/suspicious của Mendeley, không phải ground truth lừa đảo đã xác minh.

## Theo nguồn

| Nguồn | Mẫu test | FP | FN | Lỗi ≥90% tự tin | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| cresci_stock_2018 | 116 | 22 | 17 | 24 | 0.698 |
| fake_profile_post | 1590 | 0 | 0 | 0 | 1.000 |
| phishing | 159 | 0 | 7 | 7 | 0.964 |
| spam_email | 166 | 0 | 11 | 9 | 0.861 |
| twitter_bot_detection | 398 | 79 | 120 | 80 | 0.458 |

## Phát hiện chính

- `twitter_bot_detection` tạo 199/256 lỗi (77.7%); đây là nguồn gây lỗi chính.
- 178/256 lỗi (69.5%) là văn bản tối đa 12 tokens, nên text-only model thiếu ngữ cảnh để phân biệt.
- Một số false negatives trong nhóm `phishing` chứa đoạn tiểu thuyết hoặc nội dung không giống phishing; điều này là dấu hiệu label noise/semantics không đồng nhất của nguồn. Raw label phải được giữ nguyên và chỉ ghi cờ review, không sửa theo cảm tính.
- `fake_profile_post` không có lỗi trên split này dù không còn nhóm trùng chéo; khả năng cao dataset chứa template/pattern riêng rất dễ nhận ra. Kết quả này không được suy rộng thành khả năng phát hiện tài khoản giả ngoài thực tế.

## Nhóm dấu hiệu trong các lỗi

Một lỗi có thể thuộc nhiều nhóm; đây là mô tả để review, không phải nhãn mới.

| Nhóm | Số lỗi |
| --- | ---: |
| short_or_low_context | 178 |
| investment_promotion | 95 |
| other | 38 |
| account_security | 16 |
| urgency_or_action | 14 |

## Các lỗi tự tin cao cần xem trước

### phishing_2910 — false_negative (100.0%)

- Nguồn: `phishing`; actual `1`, predicted `0`.
- Từ đẩy về label 1: don, yes, turn, month, fifty.
- Từ đẩy về label 0: the, february, of, he, side.
- Preview đã ẩn định danh: "Goddess,�the scrawny man on the floor interrupted. acme deterred "Hush, my darling,�Misery whispered, "and don't be silly."She closed one of her strong hands around the rat and pulled back the spring with the other. "Oh yes. The kid was lying on his side again. "Cautiously. I don't know. For the first time in weeks��

### phishing_2980 — false_negative (100.0%)

- Nguồn: `phishing`; actual `1`, predicted `0`.
- Từ đẩy về label 1: want, me, last, fill, pain.
- Từ đẩy về label 0: he, garp, possibly, periods, folks.
- Preview đã ẩn định danh: the voice of the cynic whispered sardonically. beautiful dispelling "Dear old Geoffrey!As time passed, he became aware that there were periods of non-pain, and that these had a cyclic quality. Could one possibly play Scheherazade when one's captor was insane? No! ""Do you want the novel, or do you want me to fill out a

### phishing_2993 — false_negative (100.0%)

- Nguồn: `phishing`; actual `1`, predicted `0`.
- Từ đẩy về label 1: made, tiny, now, misery, into.
- Từ đẩy về label 0: him, he, spark, back, the.
- Preview đã ẩn định danh: He made a couple of futile tries, wadded up the paper, and gave up. bulb convince no pain, please.She rushed across the room at him, thick legs pumping, knees flexing, elbows chopping back and forth in the stale sickroom air like pistons. ""Good. All of the deaths took place following Miss Wilkes's appointment. but nei

### spam_email_1180 — false_negative (100.0%)

- Nguồn: `spam_email`; actual `1`, predicted `0`.
- Từ đẩy về label 1: 2005, security, wireless, made, computers.
- Từ đẩy về label 0: conference, and, engineering, 05, topics.
- Preview đã ẩn định danh: Subject: call for papers : the international joint conferences on computer , information and systems sciences and engineering cisse 05 if you received this email in error , please forward it to the appropriate department at your institution please do not reply to this message , your reply will not be received . if you

### spam_email_1181 — false_negative (100.0%)

- Nguồn: `spam_email`; actual `1`, predicted `0`.
- Từ đẩy về label 1: in, farmers, 100, my, get.
- Từ đẩy về label 0: europe, would, the, programme, and.
- Preview đã ẩn định danh: Subject: business intent dear sir , i am stanley woodwork , the secetary of africa white farmers co - operation ( awfc ) of zimbabwe . after the last general elections in my country where the incumbent president mr . robert mugabe won the presidential election , the government has adopted a very aggressive land reforms

### spam_email_1343 — false_negative (100.0%)

- Nguồn: `spam_email`; actual `1`, predicted `0`.
- Từ đẩy về label 1: statements, mining, 2005, in, deposits.
- Từ đẩy về label 0: the, of, power, and, on.
- Preview đã ẩn định danh: Subject: capital hill gold - chgi - potential high grade gold deposit breaking news : denver , june 14 , 2005 ( business wire ) - - capital hill gold , inc , ( chgi ) reports that the company ' s geologists are evaluating a potential high - grade bulk - tonnage gold deposit located in mineral county , nevada , the proj

### spam_email_380 — false_negative (100.0%)

- Nguồn: `spam_email`; actual `1`, predicted `0`.
- Từ đẩy về label 1: financial, sharing, investment, your, receive.
- Từ đẩy về label 0: planning, and, models, firms, market.
- Preview đã ẩn định danh: Subject: fresh , crisp leads from allmerica financial through established sponsored market programs with cpa firms , banks , credit unions and property and casualty firms , you ' ll receive the kind of leads you need to grow your client base and meet their long - term financial needs . allmerica experts will help you m

### spam_email_49 — false_negative (100.0%)

- Nguồn: `spam_email`; actual `1`, predicted `0`.
- Từ đẩy về label 1: in, disease, statements, detect, diagnostic.
- Từ đẩy về label 0: the, of, testing, and, research.
- Preview đã ẩn định danh: Subject: breaking biotech news hey , i thought you might want to take a look at gtha could genethera become the next darling of biotech ' as they announce collaborations with industry giant beckman coulter ? breaking biotech news : genethera inc . to collaborate with biotech giant beckman coulter inc . - genethera news

### phishing_6089 — false_negative (100.0%)

- Nguồn: `phishing`; actual `1`, predicted `0`.
- Từ đẩy về label 1: learn, info, days, below, make.
- Từ đẩy về label 0: phone, mailto, pm, subject, url.
- Preview đã ẩn định danh: Learn How To Make $8,000 within 7-14 days! Get out of Debt in 60 days! Please listen to the 15 minute overview calls at: [PHONE] pin [PHONE]# 3, 5, 7 & 9 PM EST Sun-Fri For a detailed info, please reply and put "Send URL" in the subject line and send it to the address below: mailto:[EMAIL]?subject=SEND_URL Warmest Rega

### cresci_2869565250 — false_positive (100.0%)

- Nguồn: `cresci_stock_2018`; actual `0`, predicted `1`.
- Từ đẩy về label 1: ethereum, bitcoin.
- Từ đẩy về label 0: —.
- Preview đã ẩn định danh: Bitcoin&litecoin&Ethereum

### cresci_779102662532947968 — false_positive (100.0%)

- Nguồn: `cresci_stock_2018`; actual `0`, predicted `1`.
- Từ đẩy về label 1: secrets, my, website, about, kids.
- Từ đẩy về label 0: ways, visit, download, create, business.
- Preview đã ẩn định danh: Visit my website o download your FREE guide to easily create passve income, effective marketig secrets & simple ways to teach kids about business.

### phishing_3210 — false_negative (100.0%)

- Nguồn: `phishing`; actual `1`, predicted `0`.
- Từ đẩy về label 1: jump, net, yell, cast, ivy.
- Từ đẩy về label 0: nick, bob, fob, mar, tip.
- Preview đã ẩn định danh: arty oboe, soil horn emu, bug rape laic boneroot reel yuft laky boat non-yell rapt grog chadkern card manyanil meek wax sag wit reefraft hazeweed tuckturfpile and?wind messbarm firm gone hue gyp tig dune pact peerpalm cast awn batePolldump no ivy nig hank sang..jump item roildrop plygaydarn il-suds nag zingneck nine pa

### spam_email_276 — false_negative (100.0%)

- Nguồn: `spam_email`; actual `1`, predicted `0`.
- Từ đẩy về label 1: money, make, system, downline, info.
- Từ đẩy về label 0: what, pm, ways, 34, 02.
- Preview đã ẩn định danh: Subject: this one will make you money 9 / 20 / 02 11 : 34 : 52 pm a great sponsor will not make you money . a great product line will not make you money either . a great compensation plan will not make you money either . a great company will not make you money either . some say it ' s a combination of the above . some

### twitter_bot_32268_330814 — false_positive (100.0%)

- Nguồn: `twitter_bot_detection`; actual `0`, predicted `1`.
- Từ đẩy về label 1: strategy, early, off, opportunity, financial.
- Từ đẩy về label 0: between, yet, build, realize.
- Preview đã ẩn định danh: Yet between realize strategy off early opportunity financial build.

### cresci_864559591039930369 — false_positive (100.0%)

- Nguồn: `cresci_stock_2018`; actual `0`, predicted `1`.
- Từ đẩy về label 1: crypto, account.
- Từ đẩy về label 0: —.
- Preview đã ẩn định danh: Crypto Esnafı / Parody Account

## Diễn giải và quyết định

- Lỗi tự tin cao cho thấy calibration chưa đáng tin; xác suất hiện tại không nên hiển thị như xác suất một vụ lừa đảo thực.
- Chênh lệch lớn theo nguồn cho thấy model học phong cách/dataset pattern. Nâng thuật toán đơn thuần sẽ không giải quyết ground-truth và source shift.
- Bước kế tiếp phù hợp là tạo một baseline text mạnh hơn trên cùng group split, rồi so sánh bằng đúng test cố định; curated/external data vẫn là cổng đánh giá cuối.
