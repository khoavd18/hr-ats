# T39 · Workflow thông báo chat W1, W2, W5

Phụ thuộc T38. Đọc spec 08, 09.

- Lưu JSON workflow và script import trong repo. Người vận hành chọn
  credential và đích gửi trong n8n.
- Kiểm HMAC và timestamp trước khi xử lý. Chống gửi lại theo event ID và
  chỉ trả ACK sau khi ghi nhận gửi thành công. Dùng mock chat khi test.
- W5 chuyển bộ đếm việc quá hạn hiện có từ lab Header Auth sang hợp đồng
  T35, giữ phạm vi **Việc của tôi** và hết hạn theo ngày Việt Nam.

W1 dùng sự kiện chấm xong. W2 dùng thay đổi stage, đặt, đổi giờ và hủy lịch
phỏng vấn. Kênh demo là Telegram, xem câu hỏi #117 và #118.
