# hr-ats

Hệ thống tuyển dụng có AI lọc CV cho HR. Kế hoạch: `docs/product/plan.md`. Quy tắc cho AI agent: `AGENTS.md`.

Agent skills được cài từ thư viện `D:\code\ai_skills` (v1.7.1, quản lý bằng `skills_manager.py`). Không sửa file trong `.agents/skills/` và `.claude/skills/`; thông tin riêng của dự án đặt trong `AGENTS.md` (ngoài khối thư viện) và `docs/`.

## Demo nhanh

ASSUMED: máy dev có Docker Desktop chạy Linux containers, Python 3.12 + `uv`,
Node.js 22.14 trở lên và các cổng localhost 5432/6379/1025/8025/8000/3000 còn trống.
Demo dùng toàn bộ dữ liệu giả, `FakeLLM`, `FakeEmbedder`, storage local, không cần
API key, model tải về hay Tesseract. Không dùng tài khoản demo cho môi trường thật.

Từ repo sạch, tại thư mục gốc (PowerShell):

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db redis mailpit
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed
uv run uvicorn app.main:app --reload
```

Nếu đã có `.env`, giữ `APP_ENV=dev`, `LLM_PROVIDER=fake`,
`EMBEDDING_PROVIDER=fake`, `STORAGE_BACKEND=local` và DB localhost.
Seed từ chối prod/provider thật/DB từ xa. Lệnh seed chạy worker đồng bộ ngay
trong tiến trình CLI, qua pipeline upload → trích text → parse → ẩn danh →
embedding → chấm điểm thật; không cần khởi động worker trước khi seed.
CLI thành công khi đủ 4 user, 3 đơn vị, 5 Job, 40 CV kỹ thuật số và 40 hồ sơ
đã chấm. Chạy lại giữ ID, kết quả AI, lịch sử và chỉnh sửa HR; không đặt lại
mật khẩu, cấp lại quyền hay tạo bằng chứng đồng ý. Lỗi giữa chừng có thể chạy
lại sau khi sửa môi trường. Các bảng interview/offer/placement/task/email mẫu
được bổ sung theo T21–T23/T25, chưa có trong M1 (câu hỏi #66).

Terminal thứ hai, từ thư mục gốc, chạy worker để xử lý các CV tải thêm:

```powershell
cd backend
uv run celery -A app.workers.celery_app worker -Q ai,email,default -l info -P solo
```

Linux/macOS bỏ `-P solo`. Terminal thứ ba, từ thư mục gốc:

```powershell
cd frontend
npm ci
npx playwright install chromium
npm run dev
```

Mở <http://localhost:3000/login>, đăng nhập `dev-recruiter@example.invalid`,
mật khẩu **`synthetic-dev-password`**. Seed cũng in tài khoản admin/lead/
recruiter2 (`dev-admin`, `dev-lead`, `dev-recruiter2` cùng miền và mật khẩu).
Mỗi tài khoản chỉ có một phiên; dùng tài khoản khác khi mở demo và E2E đồng thời.

Mở **Việc tuyển dụng**, tạo vị trí kế toán theo `data/sample_cvs/jobs.json`,
rồi kéo 5 file `cv_0008.docx`, `cv_0013.pdf`, `cv_0019.docx`, `cv_0020.docx`,
`cv_0029.pdf` vào tab **Ứng viên**. Đây là các file dành riêng, chưa nằm trong
seed. Chờ đủ 5 hồ sơ; mở dòng đầu, chọn **Không đồng ý**, chọn mức khác rồi gửi.
Mở **Kho CV**, tìm `bookkeeping`. Fake parser đọc danh sách kỹ năng có nhãn;
tên/kinh nghiệm thiếu nhãn có thể hiện **Chưa xác định**. Không suy luận chất
lượng AI thật từ demo. Nút **Xuất Excel** yêu cầu xác nhận trước khi tải.

Terminal thứ tư, sau khi API/web/worker sẵn sàng, chạy đúng lát cắt trên bằng
Playwright (từ thư mục gốc):

```powershell
cd frontend
npx playwright test m1-smoke.spec.ts
```

Bài smoke đăng nhập recruiter, tạo Job bằng form, kéo thả đúng 5 CV, đối chiếu
cả thứ tự mức AI với nhãn T06, gửi/mở lại phản hồi và tìm ứng viên của chính
lô upload trong Kho CV. Có thể chạy lại: bài test thêm comment metadata vào
bản upload để tránh trùng SHA-256 của file cũ, giữ nguyên nội dung và file gốc.
Mỗi lượt giữ lại Job/hồ sơ giả trong DB dev, không tự xoá dữ liệu.

Bộ E2E đầy đủ còn gồm các bài T04–T16 cần tài khoản/duplicate fixture riêng.
Dừng API/worker demo bằng Ctrl+C, chạy tại backend
`uv run python -m tests.ranking_browser_server` (DB/storage tạm, fake/eager,
có sẵn catalog T18), giữ web đang chạy, rồi tại frontend chạy lệnh chuẩn
`npx playwright test`. Fixture không thay DB/storage dev. Dừng fixture bằng
`New-Item -ItemType File var/t14-browser.stop` ở thư mục gốc; fixture tự dọn
đúng DB/storage của lượt đó. Khởi động lại API/worker demo khi cần dùng DB dev.

Nếu Windows giữ cổng SMTP 1025, lệnh Compose sẽ báo bind lỗi. Luồng M1 không
gửi email: có thể chạy `docker compose up -d db redis` để dùng demo, rồi xử lý
cổng Mailpit trước khi làm các task email. Không xoá volume DB để sửa lỗi cổng.

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
npx playwright test e2e/auth.spec.ts
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
| Worker Celery | Có tại T07; lệnh bên dưới, Windows thêm `-P solo` |
| Seed dev và E2E có dữ liệu | Có sau T02/T03, tại T18 |
| Đánh giá AI | Có sau T02/T03, tại T31 |

Lệnh chính xác nằm trong `docs/specs/08-testing-quality.md`. Test dùng adapter giả và không gọi mạng bên ngoài.

### Upload và worker T07/T10/T11/T12

Tại `backend/`, chạy worker bên cạnh API (cùng `.env`, DB và storage):

```sh
uv run celery -A app.workers.celery_app worker -Q ai,email,default -l info
# Windows
uv run celery -A app.workers.celery_app worker -Q ai,email,default -l info -P solo
```

`POST /api/v1/cv-files` nhận multipart field `files` lặp lại, tuỳ chọn UUID `job_id`, cookie đăng nhập và `X-CSRF-Token`. Giới hạn 50 file/lần, 10 MiB/file, nhận magic bytes PDF/DOCX/JPEG/PNG; từ chối macro. Kết quả HTTP 200 có `items` theo vị trí đầu vào, mỗi item có `index`, `cv_file`, `duplicate`, `error`; một file sai không huỷ file đúng. Xem contract đầy đủ và quyền ở spec 03/07, OpenAPI tại `/docs`.

Mặc định `STORAGE_BACKEND=local` lưu tại `var/storage` ở gốc repo, key ngẫu nhiên. GET trạng thái và download qua API có kiểm quyền/audit; storage không public. S3 dùng boto3 với `S3_BUCKET` có sẵn, endpoint/credential từ biến S3; không cần bật MinIO để dùng/test M1. Các test S3 dùng Stubber offline; runtime S3 được hoãn theo câu hỏi #8.

Worker đọc storage → trích text → che email/SĐT → gọi ba phần parse song song → tạo/cập nhật ứng viên → ẩn danh cục bộ → embedding → `done`; lỗi từng file chuyển `failed` với thông báo tiếng Việt. Mỗi kết quả parse có model/version; email lowercase và SĐT canonical lấy cục bộ. Hai CV khác định dạng cùng email/SĐT gắn cùng ứng viên; thời hạn lưu cộng `DATA_RETENTION_MONTHS` tháng lịch theo `TZ`, không tự sinh bằng chứng đồng ý. CV không có liên hệ, tên chuẩn hoá trùng và cosine > 0.95 chỉ có gợi ý `possible_duplicate_of`, không tự gộp. Có `job_id` thì T12 tạo application `new`, owner lấy từ Job và xếp hàng chấm sau commit; revision giữ application/stage/owner, tính lại kết quả AI.

Upload mới trả snapshot `pending`, GET `/api/v1/cv-files/{id}` phản ánh trạng thái hiện tại; download thêm `/download`. Worker giữ transaction đến cuối nên trạng thái có thể vẫn `pending` trong khi đang xử lý. SHA-256 trùng trả cùng ID sau kiểm quyền, không đổi Job/uploader và không tạo thêm file/activity. Nếu publish Redis lỗi, record chuyển `failed`; upload lại cùng file để thử xếp hàng lại. Lỗi parse không tự được xếp hàng lại khi upload cùng hash. Crash đúng khoảng giữa commit và publish có thể để file ở `pending`; chưa có outbox/reconciliation, cần kiểm tra vận hành trước production. Dev/test dùng CV giả; điều kiện dữ liệu thật/provider ở câu hỏi #40 chưa được chốt.

`APP_ENV=test` cấu hình eager/memory theo [Celery configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-always-eager); suite vẫn kiểm worker trên kết nối PostgreSQL riêng và upload đồng thời. T07 không đổi schema; rollback code cần dừng API/worker, giữ DB và storage, không xoá file đã nhận. Chờ review độc lập và CI xanh trước merge.

### Ẩn danh và embedding T11

`app.ai.anonymize.anonymize(text, full_name)` che tên có/không dấu, hoa/thường,
liên hệ; bỏ dòng ngày sinh/tuổi/giới tính/hôn nhân/địa chỉ, link profile cá nhân
và markup ảnh. Chỉ `candidates.anonymized_text` đi vào embedder. Đây là heuristic
đã kiểm trên 50 CV giả; chưa bảo đảm mọi CV thực tế/OCR sai (câu hỏi #46).
Pipeline lưu text và vector cùng transaction, lỗi không để bản cập nhật dở.

Dev/test giữ `EMBEDDING_PROVIDER=fake`: vector SHA-256 tất định, L2, đúng
`EMBEDDING_DIM`; không dùng fake để đánh giá chất lượng tìm kiếm ngữ nghĩa.
Local dùng sentence-transformers theo extra tuỳ chọn:

```sh
# Tại backend/, chỉ cài khi cần chạy local
uv sync --extra local-embedding
uv run --extra local-embedding celery -A app.workers.celery_app worker -Q ai,email,default -l info
# Windows thêm -P solo
```

Đặt `EMBEDDING_PROVIDER=local`, `EMBEDDING_MODEL=BAAI/bge-m3`,
`EMBEDDING_DIM=1024`. Lần dùng đầu tải trọng số về `var/models` (gitignore),
các lần sau dùng cache; model được giữ trong process. Không bật remote code,
chỉ nạp safetensors; cấu hình sai/thiếu extra/model/sai chiều trả lỗi an toàn,
không tự đổi sang fake. Tham số cache/encode theo
[SentenceTransformer](https://sbert.net/docs/package_reference/sentence_transformer/model.html).
Model local thật và chất lượng retrieval: NOT TESTED trong bộ nghiệm thu offline.

Khi đổi model/provider **cùng số chiều**, dừng API/worker và các writer/tìm kiếm,
sao lưu, cập nhật cùng cấu hình cho CLI/API/worker rồi chạy tại `backend/`:

```sh
uv run python -m app.scripts.reembed --all
# Nếu dùng local
uv run --extra local-embedding python -m app.scripts.reembed --all
```

CLI chỉ dùng `anonymized_text` đã lưu, không gửi/đọc lại CV gốc hay gọi LLM.
Một transaction thay vector ứng viên chưa xoá/chưa gộp/còn hạn và mọi Job;
clear vector ứng viên không còn hợp lệ. Thiếu text đã ẩn danh (ví dụ dữ liệu
trước T11) hoặc bất kỳ lỗi nào làm rollback toàn lượt, exit 1 và mã lỗi cố định;
cần bổ sung text qua pipeline đã duyệt trước khi chạy lại. Thành công exit 0,
in số lượng và mới bật lại API/worker cùng cấu hình. Nếu lỗi, giữ tắt writer và
khôi phục cấu hình model cũ trước khi phục vụ lại. Không trộn model trong cùng
kho vector. Đổi dimension cần migration riêng theo hướng dẫn T05 ở trên; CLI
không tự đổi cột/index. Chưa benchmark rebuild toàn kho production.

T13 dùng `app.services.embeddings.embed_job(job)` sau khi gán title/description/
must_have/nice_to_have khi tạo/sửa Job và trước commit. Hook không tự commit;
T11 không mở endpoint Job/tìm kiếm trước T13/T16.

### Chấm điểm T12

Worker `score_application` chỉ gửi `anonymized_text` và bốn trường yêu cầu Job
cho prompt `score_cv/v1`. Code kiểm đủ/đúng thứ tự tiêu chí, bằng chứng tồn tại
sau NFC/gộp khoảng trắng; thiếu hoặc bịa bằng chứng → unknown. Điểm/mức tính
cục bộ theo spec 04, lưu model/version/thời điểm và activity chỉ có level/score.
Không đổi stage hoặc gửi email. Thiếu text đã ẩn danh hoặc lỗi provider →
`ai_status=failed`, không fallback sang CV gốc. API thêm/chấm lại cần cookie/CSRF
và quyền owner/member Job (admin/lead được mọi Job):

- `POST /api/v1/applications` với `{candidate_id, job_id}` → 201, trùng active → 409.
- `POST /api/v1/applications/{id}/rescore` → 202, chấm lại một hồ sơ.
- `POST /api/v1/jobs/{id}/rescore` → 202, queue `rescore_job` chấm từng hồ sơ còn hợp lệ.

Cấu hình server trong `.env.example`: `SCORE_MUST_WEIGHT=0.75`,
`SCORE_PARTIAL_VALUE=0.5`, `SCORE_HIGH_THRESHOLD=75`,
`SCORE_UNKNOWN_THRESHOLD=0.5`, `SCORE_MIN_TEXT_LENGTH=300`.
Thay ngưỡng chỉ có hiệu lực với lượt chấm mới; dùng rescore để cập nhật hồ sơ cũ.
Publish lỗi giữ Application failed (CV đã xử lý vẫn done), thử lại bằng rescore.
Chưa có outbox: nếu process dừng giữa commit và publish, hồ sơ có thể còn pending;
sau khi broker/worker phục hồi cần chấm lại. Contract response/lỗi tại spec 03/04.
FakeLLM đọc từ khoá/kỹ năng và số năm kinh nghiệm trong CV giả, không đọc nhãn kỳ vọng;
không dùng tỷ lệ khớp fixture để kết luận chất lượng model thật.

### Trích CV và OCR T08

T08 cung cấp `app.ai.extract.extract_text(data, mime)` và
`app.ai.redact.redact_contacts(text)` cho pipeline T10. PDF kỹ thuật số đọc theo
cột, DOCX đọc cả bảng lồng nhau; ảnh JPG/PNG và trang PDF dưới 50 ký tự dùng OCR
local. PDF render 300 DPI; ảnh OCR chuyển grayscale, lọc median 3×3 giảm nhiễu scan
theo [hướng dẫn chất lượng Tesseract](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html).
Kết quả chuẩn hoá Unicode NFC, giữ xuống dòng; che
liên hệ thành `[EMAIL]`/`[PHONE]`, trả riêng email gốc và SĐT đã chuẩn hoá (`+84`
cho số Việt Nam). Không ghi các giá trị này vào log. DOCX trả `page_count=None`
vì python-docx không phân trang; PDF trả số trang thật, ảnh trả 1.

Tesseract là dependency **hệ thống**, `uv sync` không cài Tesseract. Cài trên máy
chạy worker, sau đó khởi động lại terminal/worker:

- **Windows:** dùng [installer UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
  được [tài liệu Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)
  dẫn tới; chọn thêm ngôn ngữ Vietnamese (`vie`) và English (`eng`). Thêm thư mục
  cài đặt (thường `C:\Program Files\Tesseract-OCR`) vào `PATH` của worker.
- **Docker/Debian/Ubuntu:** cài trong image worker bằng đoạn sau (Dockerfile
  triển khai đầy đủ thuộc T32):

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*
```

Kiểm tra tại cùng môi trường chạy worker:

```sh
tesseract --version
tesseract --list-langs
```

Danh sách phải có `vie` và `eng` khi dùng mặc định `TESSERACT_LANGS=vie+eng`,
`OCR_ENABLED=true`. Nếu dữ liệu ngôn ngữ ở nơi khác, đặt `TESSDATA_PREFIX` trỏ
tới thư mục tessdata chứa các file `*.traineddata` của bản cài đó. Thiếu executable
trả lỗi bắt được `ExtractionError` với thông báo **"Máy chủ chưa cài OCR"**;
thiếu ngôn ngữ/lỗi OCR có thông báo tiếng Việt chung, không phản chiếu stderr.
`OCR_ENABLED=false` vẫn đọc PDF kỹ thuật số/DOCX, nhưng file cần OCR báo chưa bật.
Text rỗng báo "Không đọc được nội dung CV". T10 chịu trách nhiệm bắt lỗi từng file
và lưu trạng thái `failed`; các hàm extract/redact T08 không tự ghi DB.

ASSUMED (giới hạn xử lý T08): tối đa 100 trang PDF, 25 triệu pixel/trang OCR hoặc
ảnh đầu vào, timeout 60 giây/lần OCR. Tái sử dụng kiểm tra file 10 MiB và an toàn
DOCX T07. PDF mã hoá hoặc file hỏng báo lỗi từng file; xem câu hỏi #34–#36. Truyền
ảnh/text qua stdin/stdout của Tesseract, không ghi file CV tạm lên đĩa.

Kiểm thử tại `backend/`:

```sh
uv run pytest tests/unit/test_extract.py tests/unit/test_redact.py -q
```

Test so nội dung với nhãn của 50 CV kỹ thuật số, thứ tự hai cột và kỹ năng trong
bảng. Test OCR thật trên 10 PDF scan và hai định dạng ảnh tự `skip` **chỉ khi
không có executable Tesseract** theo T08; máy đã cài nhưng thiếu `vie`/`eng` phải
sửa cài đặt để test pass. CI cài cả hai ngôn ngữ trước pytest. Các test còn lại
mock tại ranh giới subprocess, kiểm tra thiếu OCR/timeout/lỗi, 300 DPI và che
nhiều dạng liên hệ; không gọi provider hoặc mạng ngoài khi test.

### Thử adapter AI (T09)

Tại `backend/`, không cần DB hoặc key khi dùng fake:

```sh
uv run python -m app.scripts.llm_smoke --provider fake
uv run pytest tests/unit/test_llm.py tests/unit/test_prompts.py tests/unit/test_ai_schemas.py -q
```

Script thử ba prompt parse và một prompt score bằng dữ liệu giả cố định, chỉ in
metadata/trạng thái. Fake parse dòng có nhãn Họ tên/Kỹ năng, score bằng từ khoá,
chỉ dành cho dev/test, không đo chất lượng AI. Mặc định LLM_PROVIDER=fake giữ nguyên.

Để tự thử provider thật, đặt LLM_MODEL là model id tường minh và ANTHROPIC_API_KEY
qua môi trường hoặc `.env` đã gitignore, rồi chạy:

```sh
uv run python -m app.scripts.llm_smoke --provider anthropic
```

Có thể thêm `--model <model-id>` thay LLM_MODEL. OpenAI dùng `--provider openai`
và OPENAI_API_KEY; Ollama dùng `--provider ollama`, LLM_MODEL và OLLAMA_BASE_URL
(mặc định http://localhost:11434). Ollama cần model đã cài; script không tải model.
Base URL phải là HTTP(S) origin, không credential/path/query/fragment.

HTTPX có sẵn gọi [Anthropic tool schema](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
[OpenAI strict JSON schema](https://developers.openai.com/api/docs/guides/structured-outputs),
[Ollama chat JSON schema](https://docs.ollama.com/api/chat).
Model phải hỗ trợ tham số tương ứng và temperature=0. Timeout 60 giây mỗi pha,
max output 4096 token/lần; hai retry mạng/429/5xx và một lần sửa JSON/schema.
Log chỉ model/token/thời gian/kết quả thử, không CV/prompt/key/lỗi thô. Lỗi có
mã/thông báo cố định, script exit 1. Không tự chọn model hay đổi provider khi lỗi.

NOT TESTED: kết nối provider/model thật. Nhà cung cấp/model được duyệt và giá tiền
vẫn UNKNOWN trong [LLM contract](docs/ml/llm-contract.md); người vận hành chủ động
thử dữ liệu giả với key riêng. Pipeline T10 dùng adapter này; cần chốt chính sách parse
dữ liệu thật theo câu hỏi #40 trước production. Contract render/schema và cách
lưu client.model/prompt.prompt_version cho T10/T12: [spec 04](docs/specs/04-ai-pipeline.md).

### Đơn vị tuyển và việc tuyển dụng (T13)

Admin/lead mở **Cài đặt → Đơn vị tuyển** để thêm khách hàng hoặc phòng ban.
Tại **Việc tuyển dụng**, chọn **Tạo việc tuyển dụng**, nhập tên, đơn vị tuyển,
người phụ trách và hai danh sách yêu cầu (mỗi dòng một tiêu chí). Mở tuyển cần
ít nhất một yêu cầu bắt buộc; có thể lưu bản nháp trước. Recruiter tạo việc do
mình phụ trách và xem/sửa việc là owner hoặc thành viên; admin/lead phân công
người phụ trách khác. Danh sách có tìm kiếm, lọc trạng thái/người phụ trách và
phân trang. Ngừng dùng đơn vị bằng **Ngừng hoạt động**, kết thúc Job bằng **Đã đóng**.

Khi sửa yêu cầu của việc đã có hồ sơ, hệ thống hỏi **Chấm lại tất cả ứng viên?**
sau khi lưu. Chỉ xác nhận mới xếp hàng chấm lại qua Celery T12; huỷ giữ kết quả
hiện tại. Tạo vector dùng provider T11 đã cấu hình, mặc định fake trong dev/test.
Xem contract và giới hạn input tại [spec 03](docs/specs/03-api.md).
Tên Job mở chi tiết; nút Sửa giữ form một trang.

### Tải CV và xem xếp hạng (T14)

Mở **Việc tuyển dụng → tên vị trí → Ứng viên**, kéo thả hoặc chọn tối đa 50 CV
(PDF/DOCX/JPG/PNG, 10 MB mỗi file). Mỗi file có dòng tiến trình/lỗi riêng. Bảng
tự cập nhật mỗi 3 giây, sắp theo mức AI rồi điểm nội bộ, chỉ hiện nhãn phù hợp;
có tìm tên/chức danh/kỹ năng, lọc mức AI/bước và phân trang. File lỗi không cản
file khác; file trùng không tạo thêm dữ liệu. File đã thuộc Job khác được thông
báo chưa thêm vào vị trí này theo contract T07, không tự gắn lại.

Nhấn tên hoặc dòng ứng viên mở drawer khung (chi tiết/feedback T15); Quy trình
là khung chờ T20, Thông tin đọc yêu cầu và có link Sửa. Danh sách Job hiển thị
số ứng viên từng mức. Thêm từ kho/Xuất Excel thuộc T16/T17.

Kiểm E2E local với dữ liệu giả, không cần seed T18/API key: tại backend chạy
`uv run python -m tests.ranking_browser_server`, tại frontend `npm run dev`, rồi
`npx playwright test`. Fixture tạo DB/storage riêng, fake provider/eager Celery;
bài T14 thực sự kéo 10 CV mẫu kèm hai file lỗi. Tạo file `var/t14-browser.stop`
để dừng API graceful và dọn đúng DB/storage tạm; giữ DB dev/test và volume.
Contract/filter/sort/quyền: [spec 03](docs/specs/03-api.md); các lệnh và phạm vi
kiểm thử: [spec 08](docs/specs/08-testing-quality.md).

### Dữ liệu trong repo

Chỉ đưa CV giả vào `data/sample_cvs/` và fixture giả vào bộ test. CV thật để ngoài repo hoặc trong `var/`; dataset tải về đặt tại `var/datasets/`, file runtime tại `var/storage/`. Toàn bộ nội dung `var/` được gitignore, ngoại trừ `.gitkeep`. Giữ API key thật và cấu hình cá nhân trong `.env` đã gitignore.

T06 có sẵn 60 CV giả DOCX/PDF cùng nhãn parse và năm Job mẫu, gồm sáu nhóm nghề, sáu bố cục và PDF scan có nhiễu. Sinh lại tại `backend/` bằng `uv run python ../eval/generate_synthetic_cvs.py --count 60 --seed 20261108 --out ../data/sample_cvs`. Không cần API key hoặc mạng khi sinh; dùng dependency trong lockfile và font OFL đã commit. Hướng dẫn schema, kịch bản nhãn và kiểm tra tái lập ở [eval/README.md](eval/README.md).
