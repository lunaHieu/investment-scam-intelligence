# External text Wayback/language expansion V2

## Mục tiêu

V2 tạo một cohort ngoài hoàn toàn mới để mở rộng benchmark theo cùng cách capture
`WAYBACK_ARCHIVED_HOMEPAGE_HTML`, sau đó mới phân tầng ngôn ngữ. Mỗi tầng chỉ được mở
cho đánh giá khi có đủ cả `CONFIRMED` và `LEGITIMATE` sau hai lượt review độc lập.

Đây không phải tập train. Queue, trang lưu trữ và nội dung regulator/SEC đều bị chặn
khỏi train, tune và model scoring cho tới khi benchmark được review, cân bằng và đóng băng.

## Cohort đã khóa

- Nguồn candidate: IOSCO I-SCAN và SEC/IAPD index đã hash-pin.
- 60 `CONFIRMED_CANDIDATE` + 60 `LEGITIMATE_CANDIDATE`.
- 120 host duy nhất; không trùng với 200 host từng xuất hiện trong sáu queue trước.
- Candidate branch chỉ là provenance để đi tìm bằng chứng, chưa phải nhãn ground truth.
- Không truy cập live candidate domain; chỉ cho phép `archive.org` và `web.archive.org`.

## Checkpoint availability ngày 2026-09-30

Lượt query đầu ghi nhận:

- 120 request đã phát đi;
- 6 snapshot khả dụng ở nhánh confirmed;
- 18 câu trả lời hợp lệ không có snapshot;
- 96 request bị HTTP 429 từ Wayback;
- chưa có câu trả lời hợp lệ nào cho nhánh legitimate.

Do đó con số `0 LEGITIMATE available` không được diễn giải là không có snapshot. Nó là
trạng thái chưa biết do rate limit. Capture bị chặn cho tới khi retry giải quyết toàn bộ
lỗi và mỗi nhánh đạt tối thiểu 18 snapshot khả dụng.

## Tiếp tục an toàn

Sau khi quota Wayback hồi phục, chạy retry chậm và tạo report mới, không ghi đè report cũ:

```powershell
.\scripts\retry_wayback_language_expansion_v2.ps1 `
  -InputReport "D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\availability_report_v2.json" `
  -OutputReport "D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\availability_retry_001_v2.json" `
  -DelaySec 5 `
  -MaxAttemptsPerCandidate 2
```

Chỉ khi report retry có `unresolved_error_count = 0` và đủ hai nhánh mới chạy capture:

```powershell
.\scripts\capture_wayback_language_expansion_v2.ps1 `
  -AvailabilityReport "<clean retry report>" `
  -RawRoot "D:\nckh 2026-2027\ISI_Data\raw" `
  -CaptureDate "2026-09-30" `
  -ReportPath "D:\nckh 2026-2027\ISI_Data\derived\external_text_matched_wayback_v2\capture_report_v2.json" `
  -MinimumAvailablePerBranch 18
```

Sau capture: extract visible text, sàng lọc ngôn ngữ, xác nhận ngôn ngữ thủ công,
primary evidence review, rồi independent blinded second review. Tầng thiếu một trong hai
lớp được giữ làm reserve và không được score.
