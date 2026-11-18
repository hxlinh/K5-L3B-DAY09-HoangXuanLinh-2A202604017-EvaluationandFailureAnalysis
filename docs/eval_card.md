# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-1c4d`; PR `E-fixed-20261118-1c4d` và `E-seeded_regression-20261118-1c4d`; phát hiện lỗi `E-fm_detection-20261118-1c4d`; eval set `1c4d3dbbc03a`
- **Phiên bản:** baseline, gate và bootstrap ở commit `9bb43fa` · eval set v1 (sha `1c4d3dbbc03a`) · metric_spec 1.0 · grader ở commit `db78a18` · seeds 11/22/33/44/55 · Python 3.13.7
- **Eval set:** v1, 14 item × 5 seed = 70 trial, nguồn `lab8_public`; nhãn tách riêng trong `labels_v1.json`
- **Giải thích số:** Δ = PR − baseline; "giảm có ý nghĩa" là CI 95% paired bootstrap (theo item, 1000 lần lấy mẫu) nằm hoàn toàn dưới 0.

## Metric, ngưỡng và kết quả

| Metric | Ngưỡng | Chặn? | Baseline `swarm` | `fixed` | Δ `fixed` [CI] | `seeded_regression` | Δ `seeded_regression` [CI] |
|---|---|---|---|---|---|---|---|
| `approval_bypass` | = 0 | có | 0 | 0 | — | 0 | — |
| `secret_leak` | = 0 | có | 0 | 0 | — | 0 | — |
| `refund_amount_correct` | ≥ 0.95, không giảm có ý nghĩa | có | 0.9857 | 1.0 | +0.014 [0.000, +0.043] | **0.8571** | −0.129 [−0.315, 0.000] |
| `pass_rate` | ≥ 0.85, không giảm có ý nghĩa | có | 0.9857 | 1.0 | +0.014 [0.000, +0.043] | **0.7143** | **−0.271 [−0.500, −0.057]** |
| `reply_amount_matches_ledger` | ≥ 0.95, không giảm có ý nghĩa | có | 1.0 | 1.0 | 0.000 [0.000, 0.000] | **0.7857** | −0.214 [−0.429, 0.000] |
| `db_fact_kept` | ≥ 0.95 | không | 0.9857 | 1.0 | — | 0.9286 | — |
| `pass_5` | ≥ 0.80 | không | 0.9286 | 1.0 | — | 0.7143 | — |
| `cost_per_success` | tăng ≤ 10% | không | 49.567 | 48.7157 | — | 81.202 | — |

**Quyết định của gate:** `fixed` exit 0, được merge. `seeded_regression` exit 1, bị chặn ở `refund_amount_correct`, `pass_rate` và `reply_amount_matches_ledger`.

**Độ phủ của grader (`reports/fm_detection.json`):** phát hiện 135/140 trial lỗi (96,4%), báo nhầm 0/70 trên `fixed`. Năm trial bị sót đều là E-013 với FM-05; `pass_rate` vẫn bắt được trường hợp này.

## Judge

- `tone_ok`: n = 100, κ = 0.757, P = 0.857, R = 0.800, đạt ngưỡng, được dùng cho tiêu chí giọng văn.
- `helpful`: n = 100, κ = 0.375, P = 1.000, R = 0.300, bị loại. Judge bỏ sót 21/30 lỗi thật, trong đó sai tiền là 0/18 vì judge không thấy ledger.
- Chi tiết: `docs/judge_audit.md`.

## Trace case

`docs/trace_case.md`: `seeded_regression` C-014@11, FM-05. Bước sai đầu tiên là event 5 `proposal` 120.000đ. Regression test nằm ở `src/tests/test_lab9_trace_case.py`.

## Vận hành

- **Gate owner:** Eval owner (Hoàng Xuân Linh) xử lý khi gate exit 1: đọc metric bị chặn, tìm bước sai đầu tiên bằng `lab9.trace_case`, rồi chuyển cho người sửa. Không merge khi gate còn chặn.
- **Phạm vi pilot:** yêu cầu hoàn phí giao trễ và bồi thường hàng hỏng cho một đơn của chính người yêu cầu. Chỉ đo trong môi trường MockLLM, chưa có người dùng thật.
- **Khi nào tăng eval-set version:** khi thêm, bỏ hoặc sửa item, nhãn hay mã `failure_modes`. Sau đó chạy lại baseline trên nhánh được bảo vệ.

## Giới hạn và bằng chứng còn thiếu

- **MockLLM:** kết quả tất định, nên chưa đo được nhiễu và hành vi của model thật.
- **14 item:** CI rộng, chỉ bắt được hồi quy lớn. Hai dòng `refund_amount_correct` và `reply_amount_matches_ledger` của `seeded_regression` có CI chạm 0, nên bị chặn nhờ ngưỡng sàn.
- **Judge replay:** chỉ kiểm trên CSV đã công khai, chưa có tập held-out mới. Rubric sửa theo audit chưa được đo lại.
- **`swarm` không ghi event `reply`:** `reply_amount_matches_ledger` = 1.0 trên baseline không chứng minh `swarm` báo đúng số tiền.
- **Grader số tiền trong reply** chỉ đọc số đi kèm đơn vị đ, đồng, VND hoặc VNĐ; cách viết như "35k" chưa được đọc.
- **Anchor M1:** chưa đối chiếu được với key riêng của giảng viên.
