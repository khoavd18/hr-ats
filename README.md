# hr-ats

Hệ thống tuyển dụng có AI lọc CV cho HR. Kế hoạch: `docs/product/plan.md`. Quy tắc cho AI agent: `AGENTS.md`.

Agent skills được cài từ thư viện `D:\code\ai_skills` (v1.7.1, quản lý bằng `skills_manager.py`). Không sửa file trong `.agents/skills/` và `.claude/skills/`; thông tin riêng của dự án đặt trong `AGENTS.md` (ngoài khối thư viện) và `docs/`.

## Chạy dev

Yêu cầu: Docker Engine đang chạy Linux containers và Docker Compose v2. Chạy tại thư mục gốc repo:

```sh
docker compose config --quiet
docker compose up -d db redis mailpit
docker compose ps
```

Các giá trị mẫu `hr`/`hr` chỉ dành cho dev trên máy cá nhân. Các cổng được bind vào `127.0.0.1`.

| Dịch vụ | Địa chỉ / cấu hình dev |
|---|---|
| PostgreSQL 16 + pgvector | `localhost:5432`, user/password `hr`/`hr`, DB `hr_ats` và `hr_ats_test` |
| Redis 7 | `localhost:6379` |
| Mailpit SMTP | `localhost:1025` |
| Mailpit web | <http://localhost:8025> |

VERIFIED (cấu hình): `scripts/init-db.sql` tạo extension `vector`, `unaccent` trong cả hai DB. PostgreSQL chạy script này khi volume `db_data` còn trống. Kiểm tra sau khi dịch vụ khởi động:

```sh
docker compose exec -T db psql -U hr -d hr_ats -v ON_ERROR_STOP=1 -c "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'unaccent') ORDER BY extname;"
docker compose exec -T db psql -U hr -d hr_ats -v ON_ERROR_STOP=1 -c "SELECT datname FROM pg_database WHERE datname = 'hr_ats_test';"
docker compose exec -T redis redis-cli ping
```

Với volume dev đã tồn tại, có thể chạy lại script init mà vẫn giữ dữ liệu:

```sh
docker compose exec -T db psql -U hr -d hr_ats -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/01-init.sql
```

Dừng dịch vụ bằng `docker compose down`; volume DB được giữ lại.

### Cấu hình và MinIO tuỳ chọn

`.env.example` chứa cấu hình mẫu theo `docs/specs/01-architecture.md`, mỗi biến trên một dòng. Khi cần cấu hình ứng dụng, sao chép thành `.env` trên máy cá nhân (`Copy-Item .env.example .env` trong PowerShell); file này được gitignore. Giữ `LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake` khi dev/test. Đổi `EMBEDDING_DIM` cần migration đổi cột vector.

MinIO bật bằng profile `s3`:

```sh
docker compose --profile s3 up -d minio
```

VERIFIED (2026-11-08): lệnh bật profile trên đang bị chặn khi tải image `minio/minio` (`pull access denied`). Kiểm tra manifest `quay.io/minio/minio:latest` và tag `RELEASE.2025-09-07T16-13-09Z` cũng không thành công. [MinIO chính thức](https://github.com/minio/minio#source-only-distribution) hiện hướng dẫn build từ source. Cấu hình giữ nguyên image trong spec 01; câu hỏi #8 ở `docs/specs/open-questions.md` theo dõi quyết định về nguồn image. NOT TESTED: runtime MinIO. Ba dịch vụ dev mặc định (`db`, `redis`, `mailpit`) đã được kiểm chứng; `STORAGE_BACKEND=local` là giá trị mẫu trong `.env.example`.

Console: <http://localhost:9001>; S3 endpoint: <http://localhost:9000>. ASSUMED (mặc định dev T01): khi `S3_ACCESS_KEY`/`S3_SECRET_KEY` trống, dùng tài khoản mẫu `minioadmin`/`minioadmin`. Để thử S3, cấu hình hai biến này, tạo bucket bằng console rồi đặt `STORAGE_BACKEND=s3`, `S3_ENDPOINT=http://localhost:9000`, `S3_BUCKET` theo bucket vừa tạo. Adapter lưu trữ ứng dụng có ở task sau.

### Lệnh ứng dụng theo spec 08

Backend T02 dùng Python 3.12 và `uv` (cần có lệnh `uv` trên `PATH`). Từ thư mục gốc repo, chạy:

```sh
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

API health: <http://localhost:8000/api/v1/health>; cấu hình nhãn: <http://localhost:8000/api/v1/config/public>; tài liệu API ở <http://localhost:8000/docs> khi `APP_ENV != prod`. Settings đọc `.env` tại gốc repo; đường dẫn storage tương đối cũng tính từ gốc repo. Downgrade migration nền giữ lại các extension đã được T01 cấp sẵn.

Khi `APP_ENV=prod`, cung cấp `SECRET_KEY` ngẫu nhiên có ít nhất 32 byte UTF-8 qua môi trường; ứng dụng từ chối key mẫu `change-me` và key ngắn. Settings truyền cho `create_app(settings)` được dùng thống nhất cho API, DB và Redis.

Kiểm tra backend trong terminal khác, tại `backend/`:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

Test tự tạo schema trên DB local `hr_ats_test`, rollback từng test, dùng provider AI giả và chặn mạng ngoài. Test migration tạo/xoá DB tạm của riêng fixture để kiểm chứng trạng thái DB trống. Celery eager dùng broker trong bộ nhớ; test không cần API key thật.

Schema test được tạo hoàn toàn bằng Alembic và được đối chiếu với model để phát hiện migration thiếu table/column/index. Fixture giữ `hr_ats_test` giữa các lần chạy. Nếu chỉnh sửa migration đã áp dụng trong dev, xoá riêng DB local `hr_ats_test` rồi chạy lại `uv run pytest` để fixture tạo lại từ đầu; thao tác này làm mất dữ liệu test trong DB đó. Với migration đã merge, hãy thêm revision mới.

Log HTTP giữ method, route template, status và thời gian xử lý; log exception giữ file/dòng/hàm để chẩn đoán, đồng thời bỏ exception message, source và locals.

Các nhóm lệnh còn lại được bổ sung theo task tương ứng:

| Nhóm lệnh | Thời điểm có |
|---|---|
| Backend: cài gói, migration, chạy API, pytest, ruff, mypy | Có tại T02 |
| Frontend: cài gói (`npm ci`), chạy dev, test, lint, typecheck | Có sau T03 |
| Worker Celery | Có sau T02/T03, tại T07; Windows thêm `-P solo` |
| Seed dev và E2E có dữ liệu | Có sau T02/T03, tại T18 |
| Đánh giá AI | Có sau T02/T03, tại T31 |

Lệnh chính xác nằm trong `docs/specs/08-testing-quality.md`. Test dùng adapter giả và không gọi mạng bên ngoài.

### Dữ liệu trong repo

Chỉ đưa CV giả vào `data/sample_cvs/` và fixture giả vào bộ test. CV thật để ngoài repo hoặc trong `var/`; dataset tải về đặt tại `var/datasets/`, file runtime tại `var/storage/`. Toàn bộ nội dung `var/` được gitignore, ngoại trừ `.gitkeep`. Giữ API key thật và cấu hình cá nhân trong `.env` đã gitignore.
