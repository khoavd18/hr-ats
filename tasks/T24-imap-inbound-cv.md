# T24 · Nhận CV từ hộp mail
Mốc: M3 · Phụ thuộc: T23 · Spec: `06` (Nhận CV từ hộp mail), `04` (Luồng tổng)

## Việc cần làm
- `app/email/inbound.py` + job `poll_inbox` (Celery Beat 5 phút khi `IMAP_ENABLED`): đọc mail chưa xử lý, lấy đính kèm, tạo `cv_files(source=email)`, gắn Job theo `[JOB-xxxx]` (mã ngắn hiển thị trên Job) hoặc tên Job; lưu `inbound_emails`; sau khi parse xong và có email ứng viên → tự gửi `cv_received` (mẫu này không cần xác nhận).
- Hiển thị mã Job `[JOB-xxxx]` ở trang Job để HR dùng trong tin tuyển dụng.
- Cài đặt > Kết nối hộp mail: hiển thị trạng thái (đã bật/tắt, lần đọc gần nhất, lỗi gần nhất) — cấu hình vẫn qua biến môi trường.

## Tiêu chí nghiệm thu
- Test với IMAP giả (mock imaplib): mail có 2 đính kèm → 2 cv_files; chạy lại không tạo trùng; mail không có đính kèm → bỏ qua và ghi trạng thái.
