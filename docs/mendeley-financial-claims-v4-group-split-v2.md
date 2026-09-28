# Financial Claims V4 trên group_split_v2

## Kết luận

Rule set `MENDELEY_FINANCIAL_CLAIMS_V4` đã được tái trích xuất thành công trên
đúng phạm vi benchmark hiện hành: train và validation của `group_split_v2`.
Không có rule hoặc post-filter nào bị thay đổi trong bước này. Artifact mới vẫn
là feature giải thích được, không phải nhãn scam và chưa được phép đưa vào model
trước khi khóa thiết kế thí nghiệm bằng validation.

## Phạm vi đã khóa

| Partition | Tổng dòng trong split | Dòng được xử lý text |
| --- | ---: | ---: |
| train | 3.916 | 3.916 |
| validation | 838 | 838 |
| test | 838 | 0 |
| auxiliary | 10.607 | 0 |
| quarantine | 3 | 0 |

Đầu vào có SHA-256
`98f75387a4a598d85a6f721d10808979bda694dad8f85354d595679bdd96e734`,
khớp registry `MENDELEY_GROUP_SPLIT_V2`. Script kiểm tra hash trước khi trích
xuất và đối chiếu đủ năm partition với registry sau khi quét routing.

## Kết quả profile

Tổng cộng có 4.754 feature record và 407 record khớp ít nhất một tín hiệu,
tương đương 8,5612% phạm vi train + validation.

| Tín hiệu | Số record |
| --- | ---: |
| RETURN_RATE | 45 |
| RETURN_MULTIPLE | 6 |
| MONEY_AMOUNT | 345 |
| GUARANTEED_RETURN | 19 |
| NO_RISK | 19 |
| URGENCY_SCARCITY | 40 |
| PASSIVE_OR_EASY_INCOME | 10 |
| RECRUITMENT_REWARD | 1 |
| PAYMENT_OR_TRANSFER_REQUEST | 4 |
| ADVANCE_FEE_OR_WITHDRAWAL | 0 |
| CRYPTO_INVESTMENT_OR_PAYMENT | 22 |

Candidate ratio thấp hơn nhiều so với artifact `group_split_v1` vì
`group_split_v2` đưa toàn bộ 10.607 dòng `fake_profile_post` sang auxiliary.
Không được diễn giải chênh lệch này là rule kém hơn hoặc dữ liệu ít scam hơn.

## Kiểm tra tái lập và an toàn

- Rule-set SHA-256 giữ nguyên:
  `b992a0ee5ab657e30434730aeaf7194c98174b89039849a5a59b4a0f43328a01`.
- Hai lần chạy độc lập tạo cùng hash feature records:
  `8e222b3cace3f6c922da8044c34e9481badb73ac52fdc8b44b64449f1656badc`.
- Hai lần chạy độc lập tạo cùng hash queue:
  `25312d239b5ef201d2f71be22426c0580cbd21d22ce0f8f8f39e4519a592b21c`.
- Profile sau khi bỏ timestamp và đường dẫn output giống nhau hoàn toàn.
- Validator tái tính mọi signal từ text train/validation và xác nhận đủ 4.754
  record đúng một lần, không có trường nhãn hoặc provenance cấm trong feature.
- Không gọi mạng, không sửa raw, không phát sinh label mới.

Queue mới có 120 record thuộc 120 split group khác nhau, gồm 80 signal
candidate và 40 no-signal audit. Queue này hiện `UNREVIEWED`; nó chỉ là nguồn
audit tùy chọn, không phải label train. Bằng chứng review đã xác nhận trước đó
vẫn áp dụng cho rule set V4, nhưng không được mô tả là blind review trên chính
queue mới.

## Artifact

Các file đã lưu tại:

`D:\nckh 2026-2027\ISI_Data\derived\mendeley_investment_deceptive_2026\financial_claims_v4_group_split_v2\`

- `financial_claim_features_v4.jsonl`: 4.754 feature record.
- `profile_v4.json`: phạm vi, counts, rule fingerprint và safety contract.
- `review_queue_120.jsonl`: queue audit tùy chọn, chưa gán nhãn.

Registry đóng băng:
`registry/features/mendeley_financial_claims_v4_group_split_v2.json`.

Lệnh tái lập phải truyền cả split registry để khóa hash và counts:

```powershell
.venv\Scripts\python.exe scripts\extract_mendeley_financial_claims.py `
  --input <group-split-v2>\mendeley_v2_group_split_v2.csv `
  --output <output-dir>\financial_claim_features_v4.jsonl `
  --report <output-dir>\profile_v4.json `
  --review-queue <output-dir>\review_queue_120.jsonl `
  --feature-version MENDELEY_FINANCIAL_CLAIMS_V4 `
  --split-registry registry\splits\mendeley_group_split_v2.json

.venv\Scripts\python.exe scripts\validate_mendeley_financial_claims.py `
  --input <group-split-v2>\mendeley_v2_group_split_v2.csv `
  --features <output-dir>\financial_claim_features_v4.jsonl `
  --report <output-dir>\profile_v4.json `
  --review-queue <output-dir>\review_queue_120.jsonl `
  --feature-version MENDELEY_FINANCIAL_CLAIMS_V4 `
  --split-registry registry\splits\mendeley_group_split_v2.json
```

## Kết quả gate tiếp theo

Protocol ablation V1 đã được khóa trước khi chạy và chỉ dùng train để fit,
validation để chọn. Challenger `text + 11 claim-presence flags` không đạt ba
trong bốn gate promotion, nên giữ nguyên `text_only` và không mở test. Chi tiết
nằm tại `docs/mendeley-financial-claims-ablation-v1.md`.
