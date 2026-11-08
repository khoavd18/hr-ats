# Tiến độ

| ID | Trạng thái | Ngày | Ghi chú |
|---|---|---|---|
| T01 | done | 2026-11-08 | Ba tiêu chí nghiệm thu đạt. MinIO (profile `s3`, tuỳ chọn) hoãn lại vì image không tải được; dùng `STORAGE_BACKEND=local`. Xem câu hỏi #8. |
| T02–T33 | todo | | |

## Nhật ký
<!-- Agent thêm mục mới ở đầu: ## Txx · YYYY-MM-DD · done|blocked, rồi tóm tắt -->

## T01 · 2026-11-08 · done (chốt sau review)

Review độc lập: cả ba tiêu chí nghiệm thu đạt. Lỗi tải image MinIO không thuộc tiêu chí nghiệm thu (MinIO là profile tuỳ chọn); hoãn MinIO, dùng local storage cho tới khi triển khai thật (câu hỏi #8). Chuyển T01 từ `blocked` sang `done`.


## T01 · 2026-11-08 · blocked

VERIFIED: đã tạo cấu trúc thư mục theo spec 01 bằng `.gitkeep`; thêm Compose cho PostgreSQL 16 + pgvector, Redis 7, Mailpit và MinIO profile `s3`; volume DB/MinIO, cổng localhost, healthcheck DB/Redis và mount init SQL chỉ đọc. Script init tạo `vector`, `unaccent` trên `hr_ats` và `hr_ats_test`, chạy lại được. Thêm 35 biến mẫu đúng spec, quy tắc ignore dữ liệu/secret, EditorConfig UTF-8/LF và hướng dẫn dev. Không thêm code backend/frontend hoặc schema nghiệp vụ.

File chính: `docker-compose.yml`, `scripts/init-db.sql`, `.env.example`, `.gitignore`, `.editorconfig`, `README.md`, các `.gitkeep`, `docs/specs/open-questions.md`, `tasks/PROGRESS.md`.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Khởi động DB/Redis/Mailpit; extension và DB test tồn tại | VERIFIED — đạt | Lệnh chuẩn `docker compose up -d db redis mailpit` exit 0; `docker compose ps` cả ba healthy; truy vấn `psql` trả `vector`, `unaccent` và `hr_ats_test` |
| Mailpit web ở cổng 8025 | VERIFIED — đạt | `Invoke-WebRequest -Uri http://localhost:8025 -UseBasicParsing -TimeoutSec 10` trả HTTP 200, HTML chứa `Mailpit` |
| Không có `.env` hoặc dữ liệu thật trong repo | VERIFIED — đạt cho phạm vi thay đổi | Kiểm tra offline không có `.env` hay file CV; thư mục dữ liệu chỉ có `.gitkeep`; review toàn bộ file thay đổi chỉ có cấu hình mẫu và tài liệu |

### Lệnh kiểm chứng và kết quả

- `docker compose config --quiet` và `docker compose --profile s3 config --quiet`: pass.
- `docker compose up -d db redis mailpit`: pass sau khi khởi động Docker Desktop bằng `docker desktop start --detach`; các image dev được tải cho bước chuẩn bị môi trường.
- `docker compose ps`: DB, Redis, Mailpit đều healthy, đúng cổng localhost theo spec.
- `docker compose exec -T db psql -U hr -d hr_ats -v ON_ERROR_STOP=1 -c "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'unaccent') ORDER BY extname;"`: trả đủ hai extension.
- `docker compose exec -T db psql -U hr -d hr_ats -v ON_ERROR_STOP=1 -c "SELECT datname FROM pg_database WHERE datname = 'hr_ats_test';"`: trả DB test.
- Truy vấn extension tương tự trên `hr_ats_test`: đủ hai extension.
- `docker compose exec -T db psql -U hr -d hr_ats -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/01-init.sql`: pass khi chạy lại, các extension đã có được giữ nguyên, không tạo trùng DB.
- `docker compose exec -T redis redis-cli ping`: `PONG`.
- `Invoke-WebRequest -Uri http://localhost:8025 -UseBasicParsing -TimeoutSec 10`: HTTP 200, nội dung trang Mailpit.
- `python -` (script kiểm tra offline qua stdin): pass — cấu trúc JSON từ Compose, profile S3, image/cổng/volume, đủ 35 tên và giá trị biến khớp spec 01, placeholder và không có `.env`/file CV/code ứng dụng. Kiểm tra ignore bằng `git check-ignore --no-index --stdin` với Git metadata tạm ngoài workspace: pass cho secret, runtime, dependency, báo cáo; `.env.example` và `var/.gitkeep` được giữ. UTF-8 không BOM, LF, newline cuối và không có whitespace thừa trên các file thay đổi: pass.
- `docker compose --profile s3 up -d minio`: fail ở bước pull image `minio/minio`, `pull access denied`.
- `docker manifest inspect quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` và `docker manifest inspect quay.io/minio/minio`: đều không tìm thấy manifest.

NOT TESTED / không áp dụng cho T01: pytest, ruff, mypy, Alembic, npm test/lint/typecheck và E2E; chưa có manifest/code ứng dụng, thuộc T02/T03 và các task sau. Truy vấn DB, Redis và HTTP kiểm chứng runtime chỉ kết nối dịch vụ localhost; script offline không gọi LLM/embedding hoặc mạng ngoài. Việc tải image và tra metadata registry là bước chuẩn bị môi trường riêng. Workspace không có Git repository nên không tạo nhánh; kiểm tra ignore dùng metadata tạm và không khởi tạo `.git` trong workspace.

### Câu hỏi và việc còn lại

- Câu hỏi #5–#7 ghi các mặc định nhỏ: biến `.env` mỗi dòng, tài khoản mẫu MinIO, ngoại lệ `var/.gitkeep`.
- Blocker #8: cần duyệt nguồn image MinIO hoặc phạm vi build từ source upstream. [MinIO chính thức](https://github.com/minio/minio#source-only-distribution) hiện chỉ hướng dẫn phân phối source; không tự thay dịch vụ hoặc thêm quy trình build ngoài spec. NOT TESTED: runtime MinIO vì chưa pull được image. Giữ T01 `blocked` cho đến khi xử lý xong phần này.
- Ba dịch vụ dev đã kiểm chứng đang chạy; không xoá volume hoặc dữ liệu.
