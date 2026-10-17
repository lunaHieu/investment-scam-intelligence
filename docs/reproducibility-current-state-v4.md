# Reproducibility guide — current project state V4

Snapshot date: 2026-10-17 (Asia/Saigon).

## Tên bước và ý nghĩa

**P8R3: chuyển điểm điều hướng sang ledger V6 và executor V6.1.** Guide này là bản đồ authoritative để tái lập trạng thái hiện tại mà không dùng nhầm V5 đã tiêu thụ, executor V6 cũ hoặc capture tooling V2 chưa hỗ trợ V6. Các guide V1–V3 được giữ nguyên như snapshot lịch sử.

Guide không tải dữ liệu, tạo quyết định người review, tạo nhãn, mở partition hay chạy model.

## Biên lưu trữ và độ tin cậy

- Repository: `C:\Users\hieu\Documents\ChatGPT\invesment scam intelligence`
- Data root: `D:\nckh 2026-2027\ISI_Data`
- Python: `.venv\Scripts\python.exe`
- Chạy repository script bằng `python -m ...` từ repository root.
- Raw data nằm ngoài Git; registry đã commit phải pin SHA-256 của artifact.
- File tồn tại không đồng nghĩa đủ tin cậy. Mỗi gate cần verifier độc lập.
- Không mở live candidate domain. Availability chỉ truy cập archive endpoint theo release.

## Chuỗi bằng chứng

```text
terms/protocol
  → original bytes + SHA-256
  → offline exact-text extraction
  → entity/domain/clone/near-duplicate grouping
  → primary evidence review
  → blind independent second review
  → reconciliation + owner acceptance
  → group-disjoint development / sealed external holdout
  → predeclared model-development gate
```

Availability, registry membership và official identity không tạo label.

## Checkpoint hiện tại

### Raw và data sufficiency

- 278/278 raw files hiện có đã được xác minh, tổng 1.640.058.635 byte. Đây là 100% integrity coverage của storage hiện tại, không phải 100% acquisition plan.
- Mendeley V2: 16.202 raw rows; 5.592 benchmark-eligible; 3.916 train, 838 validation, 838 test, 10.607 auxiliary, 3 quarantine; train có 3.783 group.
- Fresh V1-Core vẫn là 0/300 validated release groups và 0 training-ready rows.
- Reference metadata, candidate count và availability count không được cộng vào train rows.

### External, Crimson và manual acquisition

- External 21 là diagnostic: 10 `CONFIRMED`, 11 `LEGITIMATE`, nhưng không có independent human evidence rereview và không phải Gold/train.
- Crimson còn 39 first-human-review task; automatic human review bị cấm.
- DFPI cần lawful first-party artifact. SSC/HNX cần official export/reuse basis hoặc written permission.
- Verified Vietnamese supply và usable image assets vẫn bằng 0.

### SEC/IAPD availability

V5 đã tiêu thụ đúng một lần: 23 request, không HTTP 429. Kết quả hiện tại:

- planned: 115;
- resolved: 107;
- available: 52;
- unavailable: 55;
- unresolved: 8, gồm 4 EXTERNAL_HOLDOUT.

V6 retry đúng tám dòng lỗi, tối đa một attempt/candidate, giãn tối thiểu 60 giây và chỉ mở sau `2026-10-18T08:47:59.207293+07:00`.

Executor authoritative là `scripts.retry_sec_edgar_iapd_wayback_availability_v6_1`. Nó tạo reservation `.partial` trước request đầu, checkpoint sau từng attempt và không tự resume partial. Không được fallback về executor V6 cũ.

### Sau availability hoàn chỉnh

Chỉ `PASS_COMPLETE_CAPTURE_PLAN_MAY_BE_PREPARED` mới cho phép dùng Capture Tooling V3:

1. `scripts.build_sec_edgar_iapd_wayback_capture_plan_v3`
2. `scripts.verify_sec_edgar_iapd_wayback_capture_plan_v3`
3. `scripts.build_sec_edgar_iapd_wayback_capture_release_v3`
4. `scripts.verify_sec_edgar_iapd_wayback_capture_release_v3`

Tooling V3 hỗ trợ V6, recompute toàn bộ 115 dòng, chọn all-and-only-available theo đúng thứ tự/cohort và yêu cầu capture `not_before` ít nhất 24 giờ sau final availability `created_at`. Không dùng V2 cho report V6.

### Model state

Historical text baseline chỉ là internal reference. Character sparse, style guard và frozen E5 đều không vượt gate. Không có fresh target corpus training-ready; training, scoring, validation/test và model promotion tiếp tục đóng.

## Lệnh xác minh chuẩn

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

.venv\Scripts\python.exe -m unittest tests.test_project_state_gap_ledger_v6 tests.test_data_sufficiency_audit_v2

.venv\Scripts\python.exe -m scripts.retry_sec_edgar_iapd_wayback_availability_v6_1 `
  --release configs\sec_edgar_iapd_wayback_availability_retry_release_v6.json `
  --verify-only

.venv\Scripts\python.exe -m unittest `
  tests.test_retry_sec_edgar_iapd_wayback_availability_v6_1 `
  tests.test_sec_edgar_iapd_wayback_capture_plan_v3 `
  tests.test_sec_edgar_iapd_wayback_capture_release_v3

.venv\Scripts\python.exe -m scripts.validate_registry
```

`--verify-only` không gửi network request. Nếu `availability_report_v6.json.partial` tồn tại, không chạy lại tự động.

## Việc được phép tiếp theo

1. Sau `not_before`, heartbeat kiểm tra Git sạch/synchronized, chạy focused/full tests và release validation.
2. Chỉ khi không có final hoặc partial V6, chạy executor V6.1 đúng một lần.
3. Chạy result verifier V6 và lưu independent QA bất biến.
4. Complete QA: chuẩn bị plan/release bằng Capture Tooling V3, nhưng vẫn chờ thêm cooldown capture.
5. Partial QA: giữ capture đóng và chỉ chuẩn bị exact unresolved-only V7 sau ít nhất 24 giờ.
6. Partial journal: không resume/rerun; bảo toàn và yêu cầu manual reconciliation.

Reviewer người thật có thể tiếp tục Crimson; chủ dự án có thể cung cấp lawful manual-source artifacts. Không được tự tạo quota filler, suy nhãn, mở validation/test/holdout hoặc thử model mới.

## Điểm bắt đầu authoritative

1. `registry/analyses/project_state_gap_ledger_v6.json`
2. `registry/analyses/data_sufficiency_audit_v2.json`
3. `registry/analyses/raw_cross_registry_provenance_audit_v2.json`
4. `registry/analyses/sec_edgar_iapd_wayback_availability_result_v5.json`
5. `registry/analyses/sec_edgar_iapd_wayback_availability_retry_release_v6.json`
6. `registry/analyses/sec_edgar_iapd_wayback_availability_result_verifier_v6.json`
7. `registry/analyses/sec_edgar_iapd_wayback_availability_v6_1_execution_hardening.json`
8. `registry/analyses/sec_edgar_iapd_wayback_capture_plan_tooling_v3.json`
9. `registry/analyses/sec_edgar_iapd_wayback_capture_execution_tooling_v3.json`
10. `registry/analyses/sec_edgar_iapd_wayback_capture_retry_tooling_v1.json`
11. `registry/analyses/crimson_human_review_packets_v2.json`
12. `registry/analyses/target_text_corpus_v1_manual_acquisition_packet_v1.json`
13. `registry/analyses/text_model_choice_dossier_v5.json`

Conversation history chỉ là ngữ cảnh, không phải artifact có thẩm quyền.
