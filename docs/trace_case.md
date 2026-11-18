# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case đã phân tích

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-014 --seed 11
python -m lab9.trace_case --shape fixed --claim C-014 --seed 11
python -m pytest -q -o addopts= tests/test_lab9_trace_case.py
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression` C-014@11, run ID `E-seeded_regression-20261118-1c4d` |
| Triệu chứng | `refund_amount_correct`, `reply_amount_matches_ledger` và `pass_rate` fail (lý do Lab 8: `proposal_mismatch`). Reply nói đã hoàn 120.000đ, ledger ghi 90.000đ, nhãn là 120.000đ |
| Bước sai đầu tiên | Event 5, `proposal`: `{"amount_vnd": 120000}` |
| Vì sao là bước *đầu tiên* | Event 2 đọc đơn đúng. Event 3 `quote` ra 150.000đ, đúng `proposal_amount` của nhãn. Event 4 `refund_history` chỉ đọc đúng khoản đã hoàn 30.000đ. Tới event 5 agent mới tự trừ 30.000đ khỏi đề xuất |
| Failure mode | FM-05 `pre_deducted` |
| Đối chứng | `fixed` C-014@11 không có event `proposal`: giữ đề xuất 150.000đ, host trừ 30.000đ và ghi đúng 120.000đ |
| Regression test | `tests/test_lab9_trace_case.py`: `test_double_deduction_is_caught` xác nhận `RefundAmountCorrect` báo sai trên `seeded_regression`; `test_fixed_shape_keeps_the_quote` xác nhận đạt trên `fixed`. Cả hai đã chạy qua |
| Chưa chắc chắn | Trace không có event cho lần host trừ tiền; việc trừ lần hai được suy ra từ ledger 90.000đ = 120.000đ − 30.000đ. MockLLM không cho biết một model thật có mắc lỗi này với tần suất nào |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
