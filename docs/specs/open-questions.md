# Câu hỏi mở

Agent ghi câu hỏi phát sinh vào đây (kèm task id và mặc định đã chọn), không tự quyết các thay đổi lớn ngoài spec.

| # | Task | Câu hỏi | Mặc định đang dùng | Trả lời |
|---|---|---|---|---|
| 1 | — | HR nội bộ hay headhunt nhiều client? | `hiring_units.kind` hỗ trợ cả hai | |
| 2 | — | Nhà cung cấp LLM nào được phép nhận CV (đã che email/SĐT)? | `fake` khi dev | |
| 3 | — | Google Workspace hay Microsoft 365 cho email/lịch? | SMTP/IMAP chung | |
| 4 | — | Ngưỡng đồng thuận AI để bật cho cả team? | Báo cáo số liệu, chưa chặn | |
| 5 | T01 | Các biến đứng cùng dòng trong ví dụ cấu hình được ghi vào `.env.example` thế nào? | ASSUMED: mỗi biến một dòng; giữ tên và giá trị trong spec 01, quote giá trị chứa khoảng trắng | |
| 6 | T01 | MinIO profile `s3` dùng tài khoản dev nào khi các biến S3 để trống? | ASSUMED: `minioadmin`/`minioadmin` chỉ cho dev, có thể đổi bằng `S3_ACCESS_KEY`/`S3_SECRET_KEY`; cổng các dịch vụ chỉ bind localhost | |
| 7 | T01 | Vừa gitignore `var/` vừa giữ placeholder thư mục thế nào? | ASSUMED: ignore `/var/*` và chỉ cho phép `/var/.gitkeep`; dữ liệu bên trong vẫn bị loại | |
| 8 | T01 | Nguồn image MinIO nào được duyệt khi image trong spec không tải được? | VERIFIED 2026-11-08: `docker compose --profile s3 up -d minio` lỗi `pull access denied`; manifest Quay `latest` và `RELEASE.2025-09-07T16-13-09Z` không tìm thấy. Giữ `minio/minio` đúng spec; runtime S3 bị chặn. [Upstream](https://github.com/minio/minio#source-only-distribution) hướng dẫn build từ source. Đề xuất thêm Dockerfile build MinIO từ source upstream đã ghim revision và cập nhật spec 01 sau khi được duyệt | Đã trả lời 2026-11-08: hoãn MinIO; dùng `STORAGE_BACKEND=local` cho dev và M1. Chọn nguồn S3 (MinIO build từ source, dịch vụ S3 tương thích khác, hoặc S3 cloud) khi làm T32 triển khai. Không chặn task nào. |
| 9 | T02 | Health trả gì khi DB hoặc Redis lỗi? | ASSUMED: thành công trả ba giá trị `ok`; dependency lỗi trả HTTP 503 theo error envelope chung, không lộ lỗi nội bộ. Contract cụ thể ghi tại spec 03 | |
| 10 | T02 | `/config/public` trả gì trước khi có stage và auth? | ASSUMED: T02 chỉ trả `hiring_unit_label`; auth theo spec 03 được triển khai tại T04, danh sách stage bổ sung khi có mô hình stage | |
| 11 | T02 | Downgrade migration extension có xoá extension do T01 tạo không? | ASSUMED: không xoá extension dùng chung khi downgrade; chỉ rollback version Alembic để tránh tác động đối tượng do hạ tầng cấp sẵn. Upgrade dùng `IF NOT EXISTS` | |
| 12 | T02 | Chứng minh migration trên DB hoàn toàn trống khi T01 đã cấp extension cho DB test? | ASSUMED: dùng DB tạm `hr_ats_test_t02_<uuid>` từ `template0`, kiểm tra upgrade/downgrade/upgrade rồi chỉ xoá DB vừa tạo; test nghiệp vụ vẫn trên `hr_ats_test`, không xoá DB dev | |
| 13 | T02 | Xử lý cảnh báo deprecation của Starlette TestClient với `httpx` thế nào? | VERIFIED: 44 test pass với `httpx` theo spec, kèm một cảnh báo đề nghị chuyển `httpx2`. Giữ dependency trong spec, không tắt cảnh báo; đánh giá lại khi nâng dependency test | Không chặn tiêu chí nghiệm thu T02 |
| 14 | T02 | Key production tối thiểu dài bao nhiêu để xử lý finding F5? | ASSUMED: từ chối key mẫu và key dưới 32 byte UTF-8 trong prod; đây là mức nền tương ứng yêu cầu 256 bit cho HS256 trong [RFC 7518 §3.2](https://www.rfc-editor.org/rfc/rfc7518#section-3.2). T04 vẫn chịu trách nhiệm chọn/cấu hình thuật toán JWT và chính sách key; test dùng key giả | Mặc định kỹ thuật theo review F5; không thay thuật toán hay triển khai auth tại T02 |
