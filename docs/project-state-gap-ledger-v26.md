# Project state and gap ledger V26

V26 thay V25 làm sổ trạng thái hiện hành sau khi hoàn tất C2-preflight.

## Thay đổi so với V25

- Cổng tiếp nhận offline đã được chuẩn hóa cho bốn nguồn CFTC, DFPI, SSC và HNX.
- CFTC/DFPI source artifact có thể đi vào QA khi file thật xuất hiện.
- SSC/HNX chỉ nhận hồ sơ quyền ở phiên bản này; source artifact vẫn bị chặn đến readiness ledger riêng.
- Template, byte/hash/source/rights verifier và tooling QA đều đã khóa SHA-256.
- Hiện chưa nhận source file, hồ sơ quyền hoặc completed submission nào.

## Trạng thái gate

- C2-preflight: hoàn tất và QA độc lập PASS.
- C2 intake: chờ genuine external artifact hoặc rights record.
- C3-preflight: hoàn tất; C3 response chờ người thật hoàn thành đúng 42 nhiệm vụ.
- C4: chưa mở vì capacity/terms/rights chưa đạt.
- A1/A2/B5 giữ nguyên trình tự và thời gian độc lập.

Không có network, candidate enumeration, capture, label, model, validation/test hoặc training operation trong C2-preflight.
