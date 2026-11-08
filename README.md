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

### Mô hình lõi T05

Revision `0003_core_data_model` thêm 10 bảng nghiệp vụ, trigger full-text `simple` + `unaccent`, index GIN và HNSW cosine. `uv run pytest` kiểm chứng đủ bảng, schema đọc, ràng buộc, tìm kiếm/vector và quyền owner/member trên PostgreSQL thật. Chưa tạo endpoint nghiệp vụ; các task tiếp theo dùng model/schema và `log_activity()` chung.

Giữ `EMBEDDING_DIM` giống nhau khi migrate và chạy app (mặc định 1024). Khi đổi model/dimension trên DB đã có dữ liệu: dừng worker ghi embedding, sao lưu, tạo revision mới xử lý embedding cũ ở cả `jobs` và `candidates`, bỏ index HNSW trước khi đổi kiểu vector rồi tạo lại, cập nhật cấu hình và tái tạo embedding từ text đã ẩn danh trước khi tiếp tục worker. Không chỉ đổi `.env` rồi chạy app: migration T05 không tự thay kích thước cột đã tồn tại. Kiểm thử migration/rollback trên bản sao trước khi chạy thật.

Rollback T05 về `0002_users` xoá 10 bảng lõi, trigger/function và enum do revision tạo; giữ bảng users và extension. `downgrade base` còn xoá users theo migration T04. Chỉ dùng rollback trên DB tạm hoặc sau khi có xác nhận và backup cho dữ liệu cần giữ; bộ test tạo DB trống riêng và tự dọn đúng DB đó. Rollout dev thông thường chỉ chạy `uv run alembic upgrade head`, không chạy downgrade trên DB dev.

### Đăng nhập và người dùng T04

Tạo admin đầu tiên tại `backend/` sau khi chạy migration:

```sh
uv run python -m app.scripts.create_admin --email admin@example.invalid
```

Thay email mẫu bằng tài khoản nội bộ của bạn. CLI hỏi mật khẩu hai lần qua stdin ẩn ký tự; mật khẩu mới có 12–128 ký tự. Không truyền mật khẩu trong tham số lệnh. CLI không ghi email/mật khẩu ra log và không ghi đè tài khoản đã tồn tại.

Mở <http://localhost:3000/login>, đăng nhập bằng tài khoản vừa tạo. Admin quản lý người dùng tại Cài đặt: tạo tài khoản, đổi vai trò, khoá/mở khoá với xác nhận. Lead không có quyền quản lý người dùng; recruiter không thấy Cài đặt. Không thể tự khoá hoặc tự bỏ quyền admin.

Access/refresh JWT nằm trong cookie HttpOnly; không lưu trong localStorage. Mỗi tài khoản có một phiên hoạt động: đăng nhập mới, logout, đổi mật khẩu hoặc đổi quyền thu hồi phiên cũ; refresh xoay token. Khoá tạm 15 phút sau 5 lần sai. API client tự thử refresh một lần khi access hết hạn. `/config/public` cũng cần đăng nhập từ T04. Contract, giới hạn input và CSRF ở spec 03/07.

Dev chạy web/API bằng cùng hostname `localhost` (khác cổng được); production dùng cùng hostname qua reverse proxy, `APP_ENV=prod` và HTTPS để cookie Secure hoạt động. Cấu hình `FRONTEND_ORIGIN` đúng origin của web.

Nghiệm thu trình duyệt với DB tạm và tài khoản giả riêng, không dùng dữ liệu dev (cần dừng API ở cổng 8000 trước):

```sh
# Terminal 1, backend/
uv run python -m tests.auth_browser_server
# Terminal 2, frontend/
npm run dev
# Terminal 3, frontend/
npx playwright test
```

Nếu chưa có Chromium: `npx playwright install chromium` (bước chuẩn bị môi trường, trước khi chạy test). Server kiểm thử chỉ bind localhost, tạo DB `hr_ats_test_t04_<uuid>` từ DB trống, migrate và seed tài khoản giả. Ctrl+C tại terminal server dừng API và xoá đúng DB tạm vừa tạo; giữ nguyên `hr_ats`/`hr_ats_test`. Không triển khai module kiểm thử này lên production. Playwright kiểm tra đăng nhập sai/đúng, điều hướng, quản lý người dùng, quyền recruiter, refresh và logout; chặn request trình duyệt ngoài localhost. Seed và E2E nghiệp vụ đầy đủ vẫn thuộc T18.

### Frontend T03

Yêu cầu Node.js 22.14 trở lên (dev/CI dùng Node 22). Tại `frontend/`:

```sh
npm ci
npm run dev
```

Mở <http://localhost:3000>. VERIFIED (phạm vi code): có thanh bên và các trang `/`, `/jobs`, `/candidates`, `/tasks`, `/reports`, `/settings`. Các màn nghiệp vụ chưa triển khai có hướng dẫn và liên kết điều hướng; T04 thêm đăng nhập, quyền Cài đặt và quản lý người dùng như trên.

Next.js đọc cấu hình riêng tại `frontend/.env.local`; có thể sao chép từ `frontend/.env.example`. `NEXT_PUBLIC_API_URL` mặc định là `http://localhost:8000/api/v1`, bao gồm tiền tố API. Đây là địa chỉ công khai, không đặt secret trong biến `NEXT_PUBLIC_*`. API client gửi cookie, nhận đường dẫn như `/jobs`; body JSON dùng `JSON.stringify`, upload dùng `FormData`. Request thay đổi dữ liệu gắn `X-CSRF-Token` từ cookie `csrf_token` hoặc `csrfToken` truyền tường minh; màn đăng nhập lấy CSRF trước khi gửi mật khẩu. Không lưu token đăng nhập trong localStorage.

Kiểm tra tại `frontend/`:

```sh
npm run lint
npm run typecheck
npm test
npm run build
```

`npm run lint` kiểm tra cả ESLint và Prettier; dùng `npm run format` để format. `npm run typecheck` sinh kiểu route qua `next typegen` rồi chạy `tsc --noEmit`, chạy được ngay sau `npm ci` mà không cần build trước; `.next/` và `next-env.d.ts` là file sinh tự động, không commit. Vitest dùng jsdom, fetch được thay bằng mock và test không gọi mạng ngoài. Bộ test gồm bốn mức AI, hàm dịch có kiểm tra kiểu, API client, hộp xác nhận và kiểm tra chuỗi JSX. Playwright đã cài và cấu hình cho localhost, chưa thêm test E2E tại T03 (theo yêu cầu task).

Dependency lồng nhau được ghim qua `overrides`: Next.js 15 dùng cùng PostCSS 8 đã vá với frontend, và parser ESLint dùng minimatch 11 đã vá. Giữ Next.js 15 theo spec; kiểm tra tương thích qua lint, typecheck, test và build khi cập nhật lockfile. CI frontend chạy `npm ci`, lint, typecheck, test và build; không cần API key hay backend để build các trang rỗng.

Các nhóm lệnh còn lại được bổ sung theo task tương ứng:

| Nhóm lệnh | Thời điểm có |
|---|---|
| Backend: cài gói, migration, chạy API, pytest, ruff, mypy | Có tại T02 |
| Frontend: cài gói (`npm ci`), chạy dev, test, lint, typecheck, build | Có tại T03 |
| Worker Celery | Có sau T02/T03, tại T07; Windows thêm `-P solo` |
| Seed dev và E2E có dữ liệu | Có sau T02/T03, tại T18 |
| Đánh giá AI | Có sau T02/T03, tại T31 |

Lệnh chính xác nằm trong `docs/specs/08-testing-quality.md`. Test dùng adapter giả và không gọi mạng bên ngoài.

### Dữ liệu trong repo

Chỉ đưa CV giả vào `data/sample_cvs/` và fixture giả vào bộ test. CV thật để ngoài repo hoặc trong `var/`; dataset tải về đặt tại `var/datasets/`, file runtime tại `var/storage/`. Toàn bộ nội dung `var/` được gitignore, ngoại trừ `.gitkeep`. Giữ API key thật và cấu hình cá nhân trong `.env` đã gitignore.

T06 có sẵn 60 CV giả DOCX/PDF cùng nhãn parse và năm Job mẫu, gồm sáu nhóm nghề, sáu bố cục và PDF scan có nhiễu. Sinh lại tại `backend/` bằng `uv run python ../eval/generate_synthetic_cvs.py --count 60 --seed 20261108 --out ../data/sample_cvs`. Không cần API key hoặc mạng khi sinh; dùng dependency trong lockfile và font OFL đã commit. Hướng dẫn schema, kịch bản nhãn và kiểm tra tái lập ở [eval/README.md](eval/README.md).
