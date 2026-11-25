# T36 · Token dịch vụ

Phụ thuộc T35. Đọc spec 03, 08, 09 và ma trận quyền T30.

- Thêm principal `integration` với token ngẫu nhiên, chỉ lưu bản băm,
  thu hồi và hết hạn được. Không dùng token dịch vụ để tạo session HR.
- Chỉ cấp scope cho ba cặp method/path đã duyệt. Kiểm rate limit và audit
  không chứa token hoặc dữ liệu ứng viên.
- Test ma trận quyền xác nhận token bị từ chối ở các endpoint còn lại.

Hai scope hoạt động là `tasks:create` và `reports:summary`. Scope
`cv:upload` trả 403 cho tới khi T42 được duyệt và có luồng consent.
