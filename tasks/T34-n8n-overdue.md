# T34 · Nhắc việc quá hạn cá nhân qua n8n

Phụ thuộc T25 và T33. Đọc spec 01, 07, 08, 09. Phạm vi là W5 cho một tài
khoản ATS và một chat riêng với workflow n8n local đã có.

## Nghiệm thu

- Celery đếm đúng các việc quá hạn thuộc tài khoản đã chọn và việc đang hiện
  trong phạm vi **Việc của tôi**. Bản nhắc được tạo tối đa một lần mỗi ngày.
- Webhook nhận đúng payload tối thiểu. Worker giữ bản nhắc và thử lại cùng
  ID trong ngày nếu webhook lỗi hoặc trả phản hồi sai. Phản hồi đúng đánh
  dấu đã gửi.
- Lịch mới tắt mặc định và có hướng dẫn bật, chạy migration, thử từ ATS dev
  với dữ liệu giả và tắt lại.
- Kiểm thử tự động dùng PostgreSQL và receiver giả. Kiểm tra Telegram đầu
  cuối dùng chat riêng với khóa local do người vận hành nhập.
