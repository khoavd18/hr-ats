# T33 · Bộ E2E hồi quy
Mốc: M5 · Phụ thuộc: T32 · Spec: `08`

## Việc cần làm
Playwright, dữ liệu seed, FakeLLM, Mailpit:
1. Admin tạo user, đơn vị tuyển, mẫu email.
2. Recruiter tạo Job, tải CV, xem xếp hạng, phản hồi AI.
3. Kéo ứng viên qua Sàng lọc → Gửi đơn vị tuyển (gửi email) → Phỏng vấn (email + .ics) → Offer → Nhận việc; hoàn tác một bước.
4. Loại một ứng viên với lý do, gửi email từ chối.
5. Task tự tạo xuất hiện; hoàn thành task.
6. Báo cáo hiện đúng số vừa thao tác.
7. Admin thực hiện yêu cầu xoá dữ liệu; ứng viên biến khỏi kho CV.
8. Recruiter khác không thấy Job không thuộc mình.

## Tiêu chí nghiệm thu
- Toàn bộ pass liên tục 3 lần chạy; thời gian chạy < 10 phút; hướng dẫn chạy trong README.
