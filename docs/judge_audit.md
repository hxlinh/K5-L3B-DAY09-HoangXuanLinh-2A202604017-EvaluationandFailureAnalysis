# Judge audit

Chạy trong `src/`: `python -m lab9.judge --csv <file> --audit 10`

`FAIL` là lớp dương, vì nhiệm vụ của judge là tìm câu trả lời lỗi.

| Tiêu chí | n | TP / FP / FN / TN | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|
| tone_ok | 100 | 24 / 4 / 6 / 66 | 0.757 | 0.857 | 0.800 | Đạt | **Dùng** cho tiêu chí giọng văn |
| helpful | 100 | 9 / 0 / 21 / 70 | 0.375 | 1.000 | 0.300 | Không đạt (κ và recall) | **Loại**, không dùng làm gate |

Tỉ lệ lỗi judge quan sát được, trước và sau hiệu chỉnh Rogan-Gladen: tone 0.28 → 0.30; helpful 0.09 → 0.30. Hai số sau hiệu chỉnh dùng sensitivity và specificity đo trên chính tập này, nên chưa phải ước lượng độc lập.

## Case audit thủ công: `judge_tone_public.csv` (đủ 10 bất đồng)

Cột "Ai đúng" dựa trên nội dung câu trả lời và cột `note` của file dữ liệu.

| # | Case | Câu trả lời (rút gọn) | Judge | Người | Ai đúng? | Hành động sửa rubric |
|---|---|---|---|---|---|---|
| 1 | H-008 | "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | Quy định xưng hô: dùng "LogiX" và "anh/chị"; xưng "em" hoặc dùng "nha" là FAIL |
| 2 | H-017 | "Dạ, bạn ơi LogiX đã hoàn… rồi nha." | PASS | FAIL | Người | Có "Dạ" không bù được việc gọi khách là "bạn" |
| 3 | H-029 | "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | Người | Câu ra lệnh hoặc ngăn khách liên hệ là FAIL, dù có từ lịch sự |
| 4 | H-042 | "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ghi rõ: ngắn nhưng lễ phép và đủ ý là PASS; không bắt buộc xin lỗi |
| 5 | H-051 | "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | Người | Cho phép thuật ngữ "refund" trong câu lịch sự |
| 6 | H-063 | "…đã hoàn 20.000đ và sẽ hoàn thêm…" | PASS | FAIL | Người | Đây là lời hứa sai sự thật, không phải lỗi giọng văn; chuyển sang kiểm tra bằng code với ledger |
| 7 | H-070 | "…đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Cấm emoji gây cười trong ngữ cảnh khiếu nại |
| 8 | H-081 | "Dạ, đơn O-107 chưa đủ điều kiện…" | FAIL | PASS | Judge | Theo `note`, người đọc nhầm ticket. Đưa case cho người thứ hai gán lại trong phiên bản nhãn mới; không sửa file công khai |
| 9 | H-088 | "Dạ, dạ, LogiX đã hoàn…" | FAIL | PASS | Người | Lỗi gõ nhỏ không đổi thái độ thì không tính là lỗi giọng văn |
| 10 | H-094 | "Da, LogiX da hoan… xin loi…" | PASS | FAIL | Người | Câu mất dấu tiếng Việt là FAIL |

Nếu H-081 được gán lại thành FAIL, kết quả tone sẽ là TP/FP/FN/TN = 25/3/6/66, P = 0.893, R = 0.806, κ = 0.784. Kết luận không đổi, nên việc giữ nguyên nhãn hiện tại không làm thay đổi quyết định dùng judge.

## Vì sao judge `helpful` bị loại

| Loại lỗi do người gán | Số case | Judge bắt được |
|---|---|---|
| sai tiền | 18 | 0 |
| sai xưng hô | 3 | 0 |
| giọng cụt | 4 | 4 |
| không hỏi lại mã đơn | 3 | 3 |
| trả lời lạc đề | 2 | 2 |

Case tiêu biểu:

| Case | Judge | Người | Ai đúng? | Hành động |
|---|---|---|---|---|
| HL-015: nói hoàn 55.000đ, ledger ghi 40.000đ | PASS | FAIL | Người | Chấm bằng metric code so reply với ledger (FM-08) |
| HL-016: xin lỗi dài, nói 55.000đ, ledger ghi 35.000đ | PASS | FAIL | Người | Như trên; lời lẽ dài và lịch sự không chứng minh số tiền đúng |
| HL-047: "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | Người | Chuyển sang tiêu chí giọng văn với rubric xưng hô mới |

## Kết luận

- **`tone_ok` được dùng** vì vượt cả ba ngưỡng. Vẫn cần sửa rubric theo bảng audit, đặc biệt là xưng hô.
- **`helpful` bị loại.** Precision 1.0 trông hoàn hảo chỉ vì judge gần như không báo FAIL: nó bỏ sót 21/30 lỗi thật (FN = 21), recall 0.3 và κ 0.375 đều dưới ngưỡng. Một gate dùng judge này sẽ cho qua phần lớn câu trả lời sai.
- **Lỗi lớn nhất của `helpful` là sai tiền (0/18)**, và judge không được xem ledger nên không có căn cứ để chấm. Tiền phải chấm bằng code, không sửa bằng cách viết lại rubric.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai, và rubric sửa theo chính các case này chưa được đo lại. Cần nhãn người mới để có tập held-out thật.
