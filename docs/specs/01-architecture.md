# 01 · Kiến trúc và stack

## Stack (đã chốt cho bản triển khai)
| Lớp | Công nghệ |
|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async không bắt buộc; dùng sync + threadpool cho đơn giản), Alembic |
| Quản lý gói Python | `uv` (`src/backend/pyproject.toml`) |
| Hàng đợi và lịch | Celery 5 + Redis; Celery Beat cho việc định kỳ |
| Cơ sở dữ liệu | PostgreSQL 16 + extension `pgvector` (image `pgvector/pgvector:pg16`) |
| Lưu file | Interface `Storage` với 2 bản: `LocalStorage` (thư mục `src/backend/var/storage`) và `S3Storage` (MinIO/S3) |
| Trích text | PyMuPDF (PDF), python-docx (DOCX), Tesseract OCR với gói `vie` + `eng` cho trang scan |
| LLM | Adapter tự viết, xem `04-ai-pipeline.md` |
| Embedding | sentence-transformers (`BAAI/bge-m3`) hoặc fake |
| Email | SMTP (`smtplib`/`aiosmtplib`), Jinja2 cho mẫu; IMAP cho nhận CV |
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, dnd-kit (kanban), Recharts (biểu đồ) |
| Test | pytest + httpx TestClient (backend), Vitest + Testing Library (frontend), Playwright (E2E) |
| Lint/format | ruff (lint + format), mypy cho `app/` ở chế độ cơ bản; ESLint + Prettier cho frontend |
| Chạy local | Docker Compose |

## Cấu trúc repo
```
hr-ats/
├── AGENTS.md / CLAUDE.md          # quy tắc phát triển
├── docker-compose.yml             # hạ tầng dev
├── docker-compose.prod.yml        # hạ tầng và app production
├── .env.example
├── src/
│   ├── backend/
│   │   ├── pyproject.toml, uv.lock
│   │   ├── alembic.ini, migrations/
│   │   ├── app/                   # API, core, models, services, email, reports, storage, workers
│   │   ├── scripts/               # khởi tạo và backup PostgreSQL
│   │   ├── tests/                 # unit/, api/
│   │   └── var/                   # storage, báo cáo HTML, Beat, backup, log API E2E
│   ├── frontend/
│   │   ├── package.json, package-lock.json
│   │   ├── src/                   # app, components, lib, i18n
│   │   ├── e2e/, scripts/
│   │   └── .next/, test-results/  # build, ảnh và trace
│   └── ai/
│       ├── pyproject.toml
│       ├── hr_ats_ai/              # extraction, anonymize, embedding, parse và score
│       │   ├── prompt_templates/   # prompt có phiên bản
│       │   └── eval/               # đánh giá, sinh bộ CV giả, checksum và font
│       └── var/                    # CV giả, model, dataset tải về, báo cáo đánh giá
├── caddy/
├── scripts/                       # điều phối task chung
├── docs/
└── tasks/
```

`hr_ats_ai` là package nội bộ được `uv sync` cài từ `src/ai/` vào môi trường
của backend. API và Celery dùng cùng package và lockfile. Git bỏ qua đầu ra
cục bộ của từng thành phần. Lệnh chạy ở [spec 08](08-testing-quality.md).

## Dịch vụ (docker-compose)
| Service | Image / lệnh | Cổng |
|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5432 |
| `redis` | `redis:7` | 6379 |
| `minio` | `minio/minio` (tuỳ chọn, profile `s3`) | 9000/9001 |
| `mailpit` | `axllent/mailpit` (SMTP giả + web xem mail) | 1025 / 8025 |
| `api` | `uvicorn app.main:app` | 8000 |
| `worker` | `celery -A app.workers.celery_app worker -Q ai,email,default` | — |
| `beat` | `celery -A app.workers.celery_app beat` | — |
| `web` | `next start` | 3000 |

Dev có thể chạy `db redis mailpit` bằng Docker và chạy `api`, `worker`, `web` trực tiếp trên máy.

T34 bổ sung một webhook tuỳ chọn tới n8n Community Edition chạy local để gửi
Telegram. Celery/Redis và PostgreSQL vẫn quản lý lịch, dữ liệu và trạng thái
gửi. Thiết lập nằm trong [spec tích hợp](09-integrations.md).

Lộ trình T35–T40 bổ sung outbox PostgreSQL và webhook ký HMAC. n8n nhận
sự kiện để thực hiện workflow thông báo và báo cáo. Quyền truy cập ATS của
n8n giới hạn theo token dịch vụ và danh sách endpoint đã duyệt. ATS giữ
quyết định nghiệp vụ, phân quyền, lịch Celery và dữ liệu tuyển dụng.

## Hàng đợi và job nền
| Queue | Job |
|---|---|
| `ai` | `process_cv_file` (trích text → parse → ẩn danh → embedding), `score_application`, `rescore_job` |
| `email` | `send_email_message`, `poll_inbox` |
| `default` | `generate_daily_report`, `generate_weekly_report`, `remind_due_tasks`, `enforce_retention` |

Mọi job phải **idempotent** (chạy lại không tạo bản ghi trùng) và cập nhật trạng thái (`*_status`, `*_error`) để UI hiển thị.

T07: `app.workers.celery_app` khai báo đủ ba queue, mặc định `default`; route các task AI vào `ai`, task email vào `email`. Chỉ nhận/serialize JSON; payload xử lý CV chỉ có UUID file. `APP_ENV=test` dùng eager và broker/backend trong bộ nhớ; dev/prod dùng `REDIS_URL`. Worker dùng session DB riêng, log qua bộ lọc PII chung. Task `process_cv_file` hiện chỉ đặt file `pending` chưa xoá thành `done`; T10 thay bằng pipeline thật. Không ghi đè file đã `done`/`running`/`failed`, chạy lại an toàn.

Storage T07 dùng key UUID hex ngẫu nhiên (32 ký tự), không chứa tên gốc/đuôi. `Storage.put(data: bytes, mime: str) -> str`, `get(key) -> bytes`, `delete(key) -> None`; delete không lỗi nếu key hợp lệ đã không còn. LocalStorage lưu ngoài web root tại `STORAGE_LOCAL_DIR`, từ chối traversal/symlink; S3Storage dùng boto3, bucket private có sẵn, không tạo bucket hay public URL. S3 dùng `S3_ENDPOINT` nếu có, ngược lại endpoint AWS mặc định; credential cấu hình hoặc chuỗi credential chuẩn boto3. Không bật profile MinIO để kiểm nghiệm thu M1 theo quyết định #8.

## Cấu hình (`.env.example`)
```
APP_ENV=dev                         # dev | test | prod
SECRET_KEY=change-me
DATABASE_URL=postgresql+psycopg://hr:hr@localhost:5432/hr_ats
REDIS_URL=redis://localhost:6379/0
STORAGE_BACKEND=local               # local | s3
STORAGE_LOCAL_DIR=var/storage
S3_ENDPOINT= S3_BUCKET= S3_ACCESS_KEY= S3_SECRET_KEY=
LLM_PROVIDER=fake                   # fake | anthropic | openai | ollama
LLM_MODEL=
SCORE_MUST_WEIGHT=0.75
SCORE_PARTIAL_VALUE=0.5
SCORE_HIGH_THRESHOLD=75
SCORE_UNKNOWN_THRESHOLD=0.5
SCORE_MIN_TEXT_LENGTH=300
ANTHROPIC_API_KEY= OPENAI_API_KEY= OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_PROVIDER=fake             # fake | local
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
OCR_ENABLED=true
TESSERACT_LANGS=vie+eng
SMTP_HOST=localhost SMTP_PORT=1025 SMTP_USER= SMTP_PASSWORD= SMTP_FROM="Tuyển dụng <tuyendung@example.com>" SMTP_TLS=false
EMAIL_RATE_LIMIT_PER_HOUR=200
LOGIN_RATE_LIMIT_PER_MINUTE=30
UPLOAD_RATE_LIMIT_PER_MINUTE=20
IMAP_ENABLED=false IMAP_HOST= IMAP_USER= IMAP_PASSWORD= IMAP_FOLDER=INBOX
HIRING_UNIT_LABEL=Đơn vị tuyển
DATA_RETENTION_MONTHS=24
FRONTEND_ORIGIN=http://localhost:3000
APP_TIMEZONE=Asia/Ho_Chi_Minh
```
Khi `EMBEDDING_DIM` đổi, cần migration đổi cột vector; ghi rõ trong README.

## Quy ước code
- Router mỏng; logic nằm ở `services/`, có test unit riêng.
- Mọi endpoint trả lỗi theo dạng `{"error": {"code": "...", "message": "<tiếng Việt cho người dùng>"}}`.
- ID dùng UUID v4; thời gian lưu UTC (`timestamptz`), hiển thị theo `APP_TIMEZONE`.
- T26: không đọc biến hệ thống `TZ` để tính ngày nghiệp vụ. `APP_TIMEZONE`
  mặc định và hiện chỉ hỗ trợ `Asia/Ho_Chi_Minh` theo phạm vi sản phẩm; giá trị
  khác báo lỗi cấu hình. `.env` cũ chỉ có TZ vẫn dùng mặc định Việt Nam; khi
  cập nhật cấu hình đổi tên sang APP_TIMEZONE. Thuộc tính Python `Settings.tz`
  giữ tương thích với các service trước đó; không thêm dependency/dịch vụ.
- Phân trang: `?page=&page_size=` (mặc định 20, tối đa 100), trả `{"items": [...], "total": n}`.
- Không đặt nội dung CV, email, số điện thoại vào log; logger có filter che PII (xem `07`).
- Frontend: mọi chuỗi hiển thị lấy từ `src/i18n/vi.ts`.
