# 01 · Kiến trúc và stack

## Stack (đã chốt cho bản triển khai)
| Lớp | Công nghệ |
|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async không bắt buộc; dùng sync + threadpool cho đơn giản), Alembic |
| Quản lý gói Python | `uv` (`backend/pyproject.toml`) |
| Hàng đợi và lịch | Celery 5 + Redis; Celery Beat cho việc định kỳ |
| Cơ sở dữ liệu | PostgreSQL 16 + extension `pgvector` (image `pgvector/pgvector:pg16`) |
| Lưu file | Interface `Storage` với 2 bản: `LocalStorage` (thư mục `var/storage`) và `S3Storage` (MinIO/S3) |
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
├── AGENTS.md / CLAUDE.md          # quy tắc agent (có khối do thư viện skill quản lý)
├── docker-compose.yml             # db, redis, minio, mailpit, (api, worker, beat, web khi build image)
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini, migrations/
│   ├── app/
│   │   ├── main.py                # tạo FastAPI app, include routers
│   │   ├── core/                  # config (pydantic-settings), db session, security, logging, errors
│   │   ├── models/                # SQLAlchemy models, 1 file / nhóm bảng
│   │   ├── schemas/               # Pydantic request/response
│   │   ├── api/                   # routers: auth, users, hiring_units, jobs, candidates, applications, ...
│   │   ├── services/              # nghiệp vụ, không phụ thuộc FastAPI
│   │   ├── ai/                    # extraction, anonymize, llm adapters, parse, score, embed, prompts loader
│   │   ├── email/                 # render mẫu, gửi SMTP, đọc IMAP
│   │   ├── reports/               # truy vấn KPI
│   │   ├── storage/               # Storage interface + impl
│   │   └── workers/               # celery app, tasks, beat schedule
│   └── tests/                     # unit/, api/, fixtures/ (chỉ dữ liệu giả)
├── frontend/
│   ├── package.json
│   └── src/ app/ (routes), components/, lib/ (api client, auth), i18n/vi.ts
├── prompts/                       # prompt có version: parse_cv/v1.md, score_cv/v1.md ...
├── eval/                          # script đánh giá AI, bộ dữ liệu đánh giá (không commit dữ liệu thật)
├── data/sample_cvs/               # CV giả do script sinh ra (được commit)
├── scripts/                       # run-task.ps1, seed, sinh CV giả
├── docs/                          # specs/, ml/, metrics/, product/, research/
└── tasks/                         # task cho agent
```

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
IMAP_ENABLED=false IMAP_HOST= IMAP_USER= IMAP_PASSWORD= IMAP_FOLDER=INBOX
HIRING_UNIT_LABEL=Đơn vị tuyển
DATA_RETENTION_MONTHS=24
FRONTEND_ORIGIN=http://localhost:3000
TZ=Asia/Ho_Chi_Minh
```
Khi `EMBEDDING_DIM` đổi, cần migration đổi cột vector; ghi rõ trong README.

## Quy ước code
- Router mỏng; logic nằm ở `services/`, có test unit riêng.
- Mọi endpoint trả lỗi theo dạng `{"error": {"code": "...", "message": "<tiếng Việt cho người dùng>"}}`.
- ID dùng UUID v4; thời gian lưu UTC (`timestamptz`), hiển thị theo `TZ`.
- Phân trang: `?page=&page_size=` (mặc định 20, tối đa 100), trả `{"items": [...], "total": n}`.
- Không đặt nội dung CV, email, số điện thoại vào log; logger có filter che PII (xem `07`).
- Frontend: mọi chuỗi hiển thị lấy từ `src/i18n/vi.ts`.
