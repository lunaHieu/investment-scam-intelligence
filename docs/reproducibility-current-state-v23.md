# Reproducibility current state V23

V23 là điểm điều hướng hiện hành sau khi cả C2-preflight và C3-preflight đã được kiểm định. Nguồn chuẩn là `registry/analyses/project_state_gap_ledger_v26.json`.

## Trạng thái tái lập được

- C2: bốn source contract, template và verifier byte/hash/source/rights đã sẵn sàng; completed submission 0.
- C3: template đúng 42 bản ghi và verifier phản hồi người duyệt đã sẵn sàng; human response 0/42.
- V1-Core: 0/300 admitted; conditional owner-accepted supply 42; residual gap 258.
- B4: release 70 dòng đã sẵn sàng nhưng availability chưa chạy.
- A1 CDX, A2 V11 và B5 giữ nguyên gate thời gian riêng.

## Phần còn phụ thuộc bên ngoài

1. C2 cần artifact/hồ sơ quyền thật; SSC/HNX chỉ được đi qua rights-record gate trước.
2. C3 cần người thật đọc 42 văn bản đã khóa hash.
3. C4 chỉ được chuẩn bị sau khi capacity, terms và rights liên quan đã PASS.
4. A1/A2/B5 tiếp tục theo automation và cooldown đã đóng băng.

Không có source acquisition, candidate enumeration, label, model scoring, validation/test hoặc training được mở bởi hai preflight này.
