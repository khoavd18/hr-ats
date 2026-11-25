# T35 · Outbox và webhook ký HMAC

Phụ thuộc T34. Đọc spec 01, 08, 09.

## Nghiệm thu

- Migration thêm `integration_events` và `webhook_endpoints`. Publisher ghi
  trong transaction của nghiệp vụ, chống tạo trùng theo endpoint và khóa sự kiện.
- Worker Celery gửi webhook với HMAC, xác nhận đúng ID, thử lại có giới hạn.
  Lượt thử lại giữ nguyên ID và payload. Endpoint đã tắt bỏ qua bản đang chờ.
- Cho phép payload theo schema và kiểm thêm bằng bộ lọc dữ liệu nhạy cảm.
  Test chữ ký, retry, chống trùng, ACK sai và payload thiếu hoặc thừa trường
  bằng dữ liệu giả.
