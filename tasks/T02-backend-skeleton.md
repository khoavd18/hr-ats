# T02 · Khung backend
Mốc: M0 · Phụ thuộc: T01 · Spec: `01-architecture.md`, `03-api.md` (Hệ thống), `07` (Logging), `08`

## Mục tiêu
FastAPI chạy được với cấu hình, DB, migration, chuẩn lỗi, log che PII và bộ test nền.

## Việc cần làm
- `backend/pyproject.toml` (uv): fastapi, uvicorn, pydantic-settings, sqlalchemy 2, psycopg[binary], alembic, pgvector, celery, redis, httpx, python-multipart, argon2-cffi, pyjwt, jinja2, openpyxl; dev: pytest, pytest-cov, ruff, mypy.
- `app/core/config.py` (Settings đọc `.env`), `db.py` (engine, session dependency), `errors.py` (exception `AppError(code, message, status)` + handler trả `{"error": {...}}`), `logging.py` (JSON log + filter che email/SĐT và các khoá `text|body|cv|content`).
- `app/main.py`: tạo app, CORS theo `FRONTEND_ORIGIN`, router `/api/v1`, `GET /api/v1/health`, `GET /api/v1/config/public` (chưa có stage thì trả nhãn đơn vị tuyển).
- Alembic cấu hình với `DATABASE_URL`, migration đầu tiên bật extension `vector`, `unaccent`.
- `tests/conftest.py`: tạo schema trên `hr_ats_test` mỗi phiên test, transaction rollback mỗi test, `TestClient`; đặt `LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake`.
- Cấu hình ruff (line-length 100), mypy cơ bản cho `app/`.

## Tiêu chí nghiệm thu
- `uv run uvicorn app.main:app` chạy; `/api/v1/health` trả `db: ok`, `redis: ok` khi hạ tầng chạy.
- `uv run pytest` pass với test cho: health, định dạng lỗi, filter log che `abc@gmail.com` và `0912 345 678`.
- `uv run ruff check .` sạch; `alembic upgrade head` chạy trên DB trống.
