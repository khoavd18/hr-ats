# T32 · Triển khai và hướng dẫn sử dụng
Mốc: M5 · Phụ thuộc: T28, T30 · Spec: `01` (Dịch vụ), `07`

## Việc cần làm
- Dockerfile cho `backend` (gồm Tesseract + gói `vie`) và `frontend`; `docker-compose.prod.yml` (api, worker, beat, web, db, redis, reverse proxy Caddy với HTTPS nội bộ hoặc theo domain).
- `docs/deploy.md`: yêu cầu máy, biến môi trường bắt buộc, khởi tạo admin, backup DB hằng ngày (`pg_dump` + giữ 14 bản), khôi phục, cập nhật phiên bản, mã hoá ổ đĩa.
- `docs/huong-dan-su-dung.md` cho HR (tiếng Việt, ngôn ngữ đời thường, mỗi việc một mục: tạo việc tuyển dụng, tải CV, đọc đánh giá AI, chuyển bước, gửi email, xem báo cáo, yêu cầu xoá dữ liệu); chừa chỗ ảnh chụp màn hình.

## Tiêu chí nghiệm thu
- `docker compose -f docker-compose.prod.yml up -d` trên máy sạch chạy được toàn hệ thống; backup và khôi phục thử thành công theo tài liệu.
