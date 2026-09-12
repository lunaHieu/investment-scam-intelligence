# Đối chiếu lỗi từng mẫu — Naive Bayes và TF-IDF Logistic Regression

## Kết quả cặp trên cùng test

| Trạng thái | Số mẫu |
| --- | ---: |
| Cả hai đúng | 2070 |
| Logistic Regression sửa được lỗi của Naive Bayes | 115 |
| Logistic Regression làm sai mẫu Naive Bayes từng đúng | 103 |
| Cả hai cùng sai | 141 |

Model mới giảm ròng 12 lỗi. Exact McNemar p-value = 0.456341; chưa đủ bằng chứng về chênh lệch có ý nghĩa ở ngưỡng 0,05.

Kiểm định này chỉ đo mức khớp với nhãn nguồn Mendeley, không chứng minh khả năng phát hiện lừa đảo thực tế.

## Phân bố theo nguồn

| Nguồn | Cả hai đúng | LR sửa được | LR làm sai thêm | Cả hai sai |
| --- | ---: | ---: | ---: | ---: |
| cresci_stock_2018 | 66 | 21 | 11 | 18 |
| fake_profile_post | 1590 | 0 | 0 | 0 |
| phishing | 146 | 4 | 6 | 3 |
| spam_email | 154 | 8 | 1 | 3 |
| twitter_bot_detection | 114 | 82 | 85 | 117 |

## Các mẫu model mới sửa được

### phishing_2980 — phishing

- Actual `1`; NB `0` (p1=0.000); LR `1` (p1=0.536).
- Preview đã ẩn định danh: the voice of the cynic whispered sardonically. beautiful dispelling "Dear old Geoffrey!As time passed, he became aware that there were periods of non-pain, and that these had a cyclic quality. Could one possibly play Scheherazade when one's captor was insane? No! ""Do you want the novel, or do you want me to fill out a

### phishing_2993 — phishing

- Actual `1`; NB `0` (p1=0.000); LR `1` (p1=0.503).
- Preview đã ẩn định danh: He made a couple of futile tries, wadded up the paper, and gave up. bulb convince no pain, please.She rushed across the room at him, thick legs pumping, knees flexing, elbows chopping back and forth in the stale sickroom air like pistons. ""Good. All of the deaths took place following Miss Wilkes's appointment. but nei

### spam_email_380 — spam_email

- Actual `1`; NB `0` (p1=0.000); LR `1` (p1=0.836).
- Preview đã ẩn định danh: Subject: fresh , crisp leads from allmerica financial through established sponsored market programs with cpa firms , banks , credit unions and property and casualty firms , you ' ll receive the kind of leads you need to grow your client base and meet their long - term financial needs . allmerica experts will help you m

### spam_email_49 — spam_email

- Actual `1`; NB `0` (p1=0.000); LR `1` (p1=0.541).
- Preview đã ẩn định danh: Subject: breaking biotech news hey , i thought you might want to take a look at gtha could genethera become the next darling of biotech ' as they announce collaborations with industry giant beckman coulter ? breaking biotech news : genethera inc . to collaborate with biotech giant beckman coulter inc . - genethera news

### cresci_779102662532947968 — cresci_stock_2018

- Actual `0`; NB `1` (p1=1.000); LR `0` (p1=0.499).
- Preview đã ẩn định danh: Visit my website o download your FREE guide to easily create passve income, effective marketig secrets & simple ways to teach kids about business.

### spam_email_276 — spam_email

- Actual `1`; NB `0` (p1=0.000); LR `1` (p1=0.689).
- Preview đã ẩn định danh: Subject: this one will make you money 9 / 20 / 02 11 : 34 : 52 pm a great sponsor will not make you money . a great product line will not make you money either . a great compensation plan will not make you money either . a great company will not make you money either . some say it ' s a combination of the above . some

### cresci_4363008376 — cresci_stock_2018

- Actual `0`; NB `1` (p1=1.000); LR `0` (p1=0.242).
- Preview đã ẩn định danh: I watch the VIX daily and short accordingly. $UVXY $SVXY $TVIX. Long Term $UBOT investor. Early Tezos $XTZ crypto investor.

### spam_email_744 — spam_email

- Actual `1`; NB `0` (p1=0.001); LR `1` (p1=0.537).
- Preview đã ẩn định danh: Subject: in financial planning time is your friend we offer personalized services designed to fit your investment strategies with over 20 years of experience , commitment and service . in financial planning , time is your friend and your enemy . lorac services offers the finest legal , tax and financial planners in the

### cresci_287885364 — cresci_stock_2018

- Actual `0`; NB `1` (p1=0.999); LR `0` (p1=0.487).
- Preview đã ẩn định danh: Specializing in great growth companies & emerging stocks, news, & events. PAID IR services. FPS is a wholly owned sub of CorporateAds, LLC [EMAIL]

### spam_email_766 — spam_email

- Actual `1`; NB `0` (p1=0.001); LR `1` (p1=0.687).
- Preview đã ẩn định danh: Subject: real time leads - no brokers your name : email address : telephone : company name : internet web site : clicking submit will send your request to op via email or call ( [PHONE] you are receiving this e - mail because you are a registered user of latimes . com , usa today , or one of our affiliates . as a regis


## Các mẫu model mới làm sai thêm

### twitter_bot_19075_648298 — twitter_bot_detection

- Actual `0`; NB `0` (p1=0.349); LR `1` (p1=0.783).
- Preview đã ẩn định danh: Direction program economy physical senior Republican choose last.

### twitter_bot_5083_480091 — twitter_bot_detection

- Actual `1`; NB `1` (p1=0.865); LR `0` (p1=0.224).
- Preview đã ẩn định danh: None save see fund they toward stage team investment town statement develop movie.

### twitter_bot_2955_713360 — twitter_bot_detection

- Actual `0`; NB `0` (p1=0.215); LR `1` (p1=0.775).
- Preview đã ẩn định danh: Describe sell huge stuff prevent thousand trip I economic cover.

### twitter_bot_16710_320739 — twitter_bot_detection

- Actual `1`; NB `1` (p1=0.750); LR `0` (p1=0.229).
- Preview đã ẩn định danh: Involve cold bill strong add operation investment give.

### twitter_bot_48725_182492 — twitter_bot_detection

- Actual `1`; NB `1` (p1=0.644); LR `0` (p1=0.245).
- Preview đã ẩn định danh: Purpose walk face growth new any interest life democratic live.

### twitter_bot_13745_615418 — twitter_bot_detection

- Actual `0`; NB `0` (p1=0.435); LR `1` (p1=0.742).
- Preview đã ẩn định danh: Sing out experience manager beautiful seem degree put hour fill.

### twitter_bot_45279_167399 — twitter_bot_detection

- Actual `0`; NB `0` (p1=0.385); LR `1` (p1=0.736).
- Preview đã ẩn định danh: Share bank cell deal course much future detail that interest property.

### twitter_bot_14887_527545 — twitter_bot_detection

- Actual `0`; NB `0` (p1=0.158); LR `1` (p1=0.722).
- Preview đã ẩn định danh: Girl structure determine three good economy among exist growth all door study.

### twitter_bot_7433_896619 — twitter_bot_detection

- Actual `0`; NB `0` (p1=0.207); LR `1` (p1=0.715).
- Preview đã ẩn định danh: Meeting own nothing base able career check itself.

### twitter_bot_33779_713362 — twitter_bot_detection

- Actual `1`; NB `1` (p1=0.798); LR `0` (p1=0.287).
- Preview đã ẩn định danh: Investment yes carry read year collection him window could certainly court home deal.


## Các mẫu cả hai cùng sai

### cresci_864559591039930369 — cresci_stock_2018

- Actual `0`; NB `1` (p1=1.000); LR `1` (p1=0.954).
- Preview đã ẩn định danh: Crypto Esnafı / Parody Account

### twitter_bot_37891_435616 — twitter_bot_detection

- Actual `1`; NB `0` (p1=0.284); LR `0` (p1=0.131).
- Preview đã ẩn định danh: Adult when fact study democratic sing method data party lose commercial investment environment.

### twitter_bot_503_614355 — twitter_bot_detection

- Actual `0`; NB `1` (p1=0.855); LR `1` (p1=0.857).
- Preview đã ẩn định danh: International claim I case event security store once notice should certain someone property.

### twitter_bot_30205_801702 — twitter_bot_detection

- Actual `1`; NB `0` (p1=0.491); LR `0` (p1=0.145).
- Preview đã ẩn định danh: Note financial drive particularly key past early figure tonight give.

### cresci_771893280833413120 — cresci_stock_2018

- Actual `1`; NB `0` (p1=0.012); LR `0` (p1=0.174).
- Preview đã ẩn định danh: Super high on Android.

### twitter_bot_47752_888756 — twitter_bot_detection

- Actual `1`; NB `0` (p1=0.276); LR `0` (p1=0.175).
- Preview đã ẩn định danh: Reach trade add hand such paper.

### twitter_bot_9871_891108 — twitter_bot_detection

- Actual `1`; NB `0` (p1=0.028); LR `0` (p1=0.181).
- Preview đã ẩn định danh: Save authority stuff property every crime side phone company statement.

### cresci_61519296 — cresci_stock_2018

- Actual `1`; NB `0` (p1=0.433); LR `0` (p1=0.182).
- Preview đã ẩn định danh: Investment Banker, Advisor, Entrepreneur, Investor, An idealist. Love challenges!

### twitter_bot_17434_558863 — twitter_bot_detection

- Actual `1`; NB `0` (p1=0.188); LR `0` (p1=0.183).
- Preview đã ẩn định danh: Best gas front simple business measure common my run or trade decide fund.

### twitter_bot_27453_883963 — twitter_bot_detection

- Actual `1`; NB `0` (p1=0.006); LR `0` (p1=0.186).
- Preview đã ẩn định danh: President admit of shake six pass say join form watch economy heart plant.

## Quyết định

- Logistic Regression tốt hơn nhẹ về tổng số lỗi, nhưng hai model trao đổi nhiều lỗi khác nhau.
- Giữ cả hai kết quả để tái lập; chọn Logistic Regression làm baseline nội bộ chính vì cross-source macro tốt hơn.
- Các mẫu cả hai cùng sai và các regression tự tin cao phải được dùng làm error set; không sửa raw label nếu chưa có evidence độc lập.
