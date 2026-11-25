# T38 · Trang Tích hợp

Phụ thuộc T35, T36, T37. Đọc spec 03, 08, 09.

- Giao diện quản trị tiếng Việt để bật/tắt từng tích hợp, gửi thử và đọc
  nhật ký giao sự kiện. Không hiển thị khóa, raw request hay response.
- API xác thực quyền quản trị, ghi audit cho các thao tác thay đổi.
- E2E dùng một webhook receiver giả để kiểm bật/tắt, gửi thử, xác nhận
  trạng thái thành công và lỗi.
