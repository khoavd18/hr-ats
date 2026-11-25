# T37 · Hạ tầng n8n

Đọc spec 01, 08, 09 và hướng dẫn deploy.

- Thêm n8n trong profile Compose `automation`, database và thông tin kết
  nối riêng. Cấu hình Caddy và biến môi trường bảo mật cho n8n.
- Bổ sung hướng dẫn khởi động, tắt và backup/restore database n8n.
- Kiểm render Compose khi có và khi không có profile, healthcheck n8n
  và restore bản backup thử vào database cô lập.
