# Tiến độ

| ID | Trạng thái | Ngày | Ghi chú |
|---|---|---|---|
| T01 | done | 2026-11-08 | Ba tiêu chí nghiệm thu đạt. MinIO (profile `s3`, tuỳ chọn) hoãn lại vì image không tải được; dùng `STORAGE_BACKEND=local`. Xem câu hỏi #8. |
| T02 | done | 2026-11-08 | Review lần 2: APPROVE WITH NITS, 76 test pass trên Postgres/Redis thật (tasks/reviews/T02.md). Nhắc việc N1→T05, N2→T14, N3→T26. |
| T03 | review | 2026-11-08 | VERIFIED: khung frontend Next.js 15, sáu trang tiếng Việt, API client và bộ component; 39 test pass, lint/typecheck/build sạch, smoke Chromium 1280px đạt. Chờ review và merge. |
| T04–T33 | todo | | |

## Nhật ký
<!-- Agent thêm mục mới ở đầu: ## Txx · YYYY-MM-DD · done|blocked, rồi tóm tắt -->

## T03 · 2026-11-08 · review

VERIFIED: triển khai đúng phạm vi T03 theo `tasks/_implement.md` trên nhánh `task/T03-frontend-skeleton`. T01 đã `done`, working tree sạch trước khi bắt đầu. Chờ review và merge; chưa chuyển task thành `done`.

- Next.js 15.5.29 App Router, React 19, TypeScript strict, Tailwind 3.4, TanStack Query; ESLint + Prettier, Vitest + Testing Library, Playwright; lockfile npm và scripts dev/build/start/lint/typecheck/test/format. Typecheck sinh kiểu route bằng `next typegen` trước `tsc`; không commit `.next/`, `next-env.d.ts` hay cache.
- Bộ shadcn/ui từ CLI chính thức: button, input, table, dialog, sheet (drawer), sonner (toast), badge, tabs, select, dropdown-menu. Nhãn đóng và nhãn trợ năng toast đều lấy từ `vi.ts`; bỏ dependency theme không dùng. Component chung: `AiLevelBadge` bốn mức đúng nhãn/màu, `EmptyState`, `ConfirmDialog`, `PageHeader`.
- Thanh bên sáu mục, trạng thái đang chọn, liên kết bỏ qua điều hướng bằng bàn phím, vùng tài khoản chưa đăng nhập; sáu trang rỗng có hướng dẫn và liên kết hoạt động, loading/error/404 tiếng Việt. Chưa thêm thao tác nghiệp vụ hay dữ liệu giả làm dữ liệu thật.
- `vi.ts` có `t()` giới hạn key bằng TypeScript; test kiểm tra key/kiểu trả về và dùng AST để phát hiện chuỗi JSX/nhãn trợ năng viết cứng. API client gửi cookie, gắn CSRF cho request thay đổi dữ liệu, giữ FormData/signal, xử lý phản hồi rỗng, lỗi và huỷ request. Không hiển thị raw message từ server, không log payload/token.
- `ConfirmDialog` chỉ gọi thao tác sau nút xác nhận, chặn đóng/gửi lặp khi đang xử lý, giữ mở khi lỗi; focus ban đầu vào Huỷ và trả về nút mở khi đóng. Regression test tái hiện lỗi trả focus trước khi sửa.
- Thêm job CI frontend: npm ci → lint → typecheck → test → build. README hướng dẫn dev, biến môi trường riêng của frontend, cách dùng API client và kiểm tra. Giữ Next.js 15 theo spec; override có phạm vi cho PostCSS 8 và minimatch 11 để xử lý audit dependency lồng nhau, không đổi framework.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| `npm run dev` mở các trang, điều hướng bằng thanh bên | VERIFIED — đạt | Dev server localhost:3000 chạy; Chromium click đủ sáu mục, tiêu đề/trạng thái đang chọn/trạng thái rỗng đúng, tải trực tiếp cả sáu trang HTTP 200; liên kết hành động hoạt động. Bố cục 1280×800 không tràn, skip link dùng được bằng bàn phím, 404 tiếng Việt, không lỗi JavaScript hay request ngoài localhost |
| Lint, typecheck, test pass; có test `AiLevelBadge` và `t()` | VERIFIED — đạt | `npm run lint`, `npm run typecheck` pass; `npm test`: **39 passed**, 5 file; test đủ bốn mức AI và kiểm tra kiểu key dịch; thêm test API client và hộp xác nhận |
| Không có chuỗi hiển thị viết cứng ngoài `vi.ts` | VERIFIED — đạt trong phạm vi frontend | Test AST `src/test/i18n-usage.test.ts` pass; tự review text/metadata/aria-label, nhãn Dialog/Sheet/Sonner, thông báo lỗi và màn hình thực tế |

### Lệnh kiểm chứng

- `npm ci`: pass, 536 package được cài từ lockfile, audit **0 vulnerabilities** (cho phép truy cập registry chỉ trong bước cài dependency; test không gọi mạng ngoài). Đã kiểm tra `npm ls postcss minimatch`: PostCSS 8.5.32 dùng chung, parser ESLint dùng minimatch 11.0.5, không còn dependency invalid.
- `npm run lint`: pass, ESLint không warning; toàn bộ file khớp Prettier.
- `npm run typecheck`: pass (`next typegen && tsc --noEmit`).
- `npm test`: **39 passed**, không skip; fetch được mock, dữ liệu test chỉ là chuỗi/token tổng hợp, không gọi LLM/embedding hay mạng ngoài.
- `npm run build` với `NEXT_TELEMETRY_DISABLED=1`: pass; sáu trang rỗng, 404 và icon được build tĩnh. Không cần API đang chạy hoặc API key.
- `npm run dev` và `npm run start`: ready ở localhost:3000; smoke trình duyệt pass trên cả dev và production. `npx playwright install chromium` chuẩn bị trình duyệt; `node ../var/t03-browser-smoke.mjs` tại `frontend/`: pass các kiểm tra trình duyệt nêu trên. Đã xem ảnh 1280×800 sau khi hiệu ứng chuyển màu kết thúc: chữ tiếng Việt rõ, mục đang chọn đúng màu, không tràn. Script smoke và ảnh `var/t03-overview.png` chỉ là artifact local được gitignore; không thêm test E2E vào repo theo phạm vi T03. Các server kiểm chứng đã được dừng.
- `git diff --check`: sạch. Tự review: không đổi API/schema/KPI, không có CV, thông tin liên hệ hay secret thật trong thay đổi; chỉ sửa frontend, CI và tài liệu liên quan.

File chính: `frontend/package.json`, `package-lock.json`, `src/app/`, `src/components/`, `src/i18n/vi.ts`, `src/lib/api.ts`, các cấu hình/test frontend, `.github/workflows/ci.yml`, `.gitignore`, README, spec 08, câu hỏi mở và `tasks/PROGRESS.md`.

ASSUMED: các mặc định nhỏ ghi ở câu hỏi #15–#17 (base URL/CSRF, tài khoản và trang rỗng trước T04, lựa chọn Sonner/Tailwind). Không có blocker. Auth, quyền Cài đặt và cấp/kiểm tra CSRF do T04 hoàn thiện.

NOT TESTED: GitHub Actions trên remote (chưa push), E2E nghiệp vụ có backend/seed (T18). Backend test/lint/migration không áp dụng vì T03 không sửa backend hay schema. Cài dependency có cảnh báo deprecation của ESLint 9 và `whatwg-encoding` từ jsdom; không tắt cảnh báo, không nâng major ngoài bộ Next.js 15; lint/test/build đều pass.

## Bảo trì script · 2026-11-08 · cờ Codex CLI

VERIFIED: log `var/auto-task/run-20261108-122052.log` ghi lỗi `unexpected argument '--full-auto'`. Tái hiện trên Codex CLI npm 0.167.0: cờ cũ trả exit 2 ngay khi phân tích tham số, trước khi triển khai T03.

- Đổi sang `--approve-for-me` trong `scripts/auto-task.ps1` và `scripts/run-task.ps1`; giữ tham số PowerShell `-FullAuto` của script chạy một task. Theo [OpenAI Docs](https://learn.chatgpt.com/docs/non-interactive-mode#permissions-and-safety), cờ này dùng sandbox `workspace-write` và chuyển yêu cầu cấp quyền qua bước xét duyệt tự động.
- Kiểm chứng: parser PowerShell 5.1 đọc cả hai script không có lỗi; CLI thật chấp nhận bộ tham số tự động và mặc định với `--version`, đều exit 0; `git diff --check` sạch. Kiểm tra tham số không gọi mô hình.
- NOT TESTED: chưa chạy lại toàn luồng triển khai, review, CI và merge. Giữ nguyên trạng thái task; chưa triển khai T03 trong lần sửa script này. Cần commit thay đổi trước khi chạy lại vì `auto-task.ps1` yêu cầu repo sạch.

## T02 · 2026-11-08 · review · Fix round 1

VERIFIED: sửa F1–F7 trong `tasks/reviews/T02.md` theo `tasks/_fix.md`; giữ nhánh `task/T02-backend-skeleton`, chờ review lại trước khi merge.

- Giữ stack file/dòng/hàm đã lọc thay vì bỏ toàn bộ traceback; không giữ message exception, source, locals hay đường dẫn đầy đủ.
- Bỏ `create_all` khỏi fixture; schema chỉ qua Alembic, có đối chiếu model/schema và test phát hiện thiếu table/column/index.
- Thu hẹp redaction để giữ metadata chẩn đoán và số thập phân; vẫn che email/SĐT/CV/secret key và giá trị nhạy cảm lồng nhau.
- Truyền Settings riêng của app tới DB/Redis; thêm guard key production và log HTTP chỉ có metadata an toàn.
- README ghi cách xử lý DB test khi sửa migration đã áp dụng; cập nhật spec 07/08 và câu hỏi #14. Không tự reset DB test hoặc thêm dependency.

Kiểm chứng cuối: `uv run pytest` **76 passed, 1 warning**; `uv run ruff check .`, `uv run ruff format --check .` (28 file), `uv run mypy app` (17 file), `uv run alembic upgrade head` đều pass. Test DB/migration riêng **7 passed**. Chạy thật Uvicorn thường và `--reload`: health, config, log HTTP đạt. `git diff --check` sạch; không còn DB tạm của T02, các tiến trình smoke đã dừng.

File chính: `backend/app/core/logging.py`, `errors.py`, `db.py`, `redis.py`, `config.py`, `middleware.py`, `backend/app/main.py`, fixture/test backend, README, spec 07/08, câu hỏi mở, `tasks/reviews/T02.md`. Báo cáo fix ghi từng finding, bằng chứng test và nguyên văn warning `httpx2` đã đối chiếu với source Starlette đang cài. Chờ review lại; trạng thái giữ `review`.

## T02 · 2026-11-08 · review

VERIFIED: hoàn thành triển khai theo `tasks/_implement.md` trên nhánh `task/T02-backend-skeleton`. Chờ review và merge trước khi chuyển trạng thái thành `done`.

### Thay đổi

- Python 3.12, uv và lockfile; đủ dependency backend/dev theo T02; cấu hình pytest, ruff (100 ký tự), mypy cơ bản cho `app/`.
- Settings đọc `.env` UTF-8 tại gốc repo, cấu hình mẫu theo spec 01, secret được che trong repr; storage tương đối tính từ gốc repo.
- Engine/session SQLAlchemy sync; Alembic lấy `DATABASE_URL`; migration đầu bật `vector`, `unaccent` bằng `IF NOT EXISTS`. Downgrade giữ extension do T01 có thể đã cấp sẵn; chưa thêm bảng nghiệp vụ.
- Hai endpoint hệ thống `/api/v1/health`, `/api/v1/config/public`; service kiểm tra DB/Redis với timeout; response model và schema lỗi trong OpenAPI. CORS chỉ origin cấu hình, kể cả phản hồi 500; docs/OpenAPI tắt ở prod.
- `AppError`, lỗi HTTP/validation/ngoài dự kiến trả envelope tiếng Việt; không phản chiếu input, exception detail hay stack trace.
- JSON logging che email/SĐT, dữ liệu nhạy cảm lồng nhau, PII trong khoá JSON và credential URL; loại nội dung exception/stack và access URL để tránh log dữ liệu cá nhân.
- Fixture chỉ dùng DB localhost `hr_ats_test`, transaction/savepoint rollback cả sau `session.commit()`, DB tạm riêng để test migration từ trạng thái trống. Provider AI giả, Celery eager/broker bộ nhớ, email trong bộ nhớ, chặn DNS/kết nối ngoài localhost. Toàn bộ dữ liệu test là giả.
- Cập nhật README, spec 03/08, câu hỏi #9–#13 và ignore cache kiểm thử.

File chính: `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/main.py`, `backend/app/core/`, `backend/app/api/system.py`, `backend/app/services/system.py`, `backend/migrations/`, `backend/tests/`, `README.md`, `.gitignore`, `docs/specs/03-api.md`, `docs/specs/08-testing-quality.md`, `docs/specs/open-questions.md`.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Uvicorn chạy; health trả DB và Redis `ok` | VERIFIED — đạt | Chạy thật cả `uv run uvicorn app.main:app` và `uv run uvicorn app.main:app --reload`; HTTP localhost:8000 trả `{"status":"ok","db":"ok","redis":"ok"}`. HTTP config/public và CORS cũng đúng cấu hình |
| Pytest pass; có test health, định dạng lỗi, filter log che ví dụ giả trong T02 | VERIFIED — đạt | `uv run pytest`: 44 passed, 1 warning. Có integration test health trên PostgreSQL/Redis thật, lỗi 503, error envelope, validation không lộ input, log che email/SĐT và trường nhạy cảm lồng nhau |
| Ruff sạch; Alembic upgrade head chạy trên DB trống | VERIFIED — đạt | `uv run ruff check .` pass; `uv run ruff format --check .` 25 file đúng định dạng; `uv run mypy app` sạch 16 file. Lệnh CLI `uv run alembic upgrade head` chạy trên DB dev và DB tạm tạo từ `template0`, xác nhận đủ hai extension và revision head |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, ba dịch vụ đang chạy.
- `uv sync` (tại `backend/`): pass với Python 3.12.16; lockfile 65 package, 64 dependency cài trong venv. Đã chuẩn bị `uv` 0.13.7 và lệnh có trên PATH của máy.
- `uv run pytest`: lần cuối **44 passed, 1 warning**, không skip. Cảnh báo upstream `StarletteDeprecationWarning` về `httpx` được giữ nguyên, xem câu hỏi #13.
- `uv run ruff check .`: pass.
- `uv run ruff format --check .`: pass, 25 file đúng định dạng.
- `uv run mypy app`: pass, không có lỗi trên 16 file.
- `uv run alembic upgrade head`: pass trên DB dev local. Lặp lại đúng CLI trên DB tạm hoàn toàn mới từ `template0`: pass; kiểm tra `pg_extension` có `vector`, `unaccent`, `alembic_version` là `0001_enable_extensions`; DB tạm được dọn.
- `uv run uvicorn app.main:app` và `uv run uvicorn app.main:app --reload`: đều pass kiểm tra HTTP thật cho health/config/CORS. Chỉ tiến trình smoke test được dừng sau kiểm tra; không còn listener kiểm thử ở cổng 8000.
- Test Alembic integration: upgrade → downgrade → upgrade trên DB trống pass, giữ extension khi rollback; SQL offline đúng. Test session commit xác nhận dữ liệu vẫn nằm trong transaction ngoài và bị rollback sau test.
- Hai lỗi phát hiện khi tự review (PII trong khoá JSON, CORS của lỗi 500) có test tái hiện thất bại trước khi sửa; chạy lại regression và toàn bộ suite đều pass.
- `git diff --check`: pass. Kiểm tra offline các file thay đổi: UTF-8/LF, không BOM; không track `.env`, venv, file CV hoặc dữ liệu thật. Đã đọc toàn bộ diff mã nguồn/test/spec trước commit.
- Kiểm tra cleanup cuối: không còn DB `hr_ats_test_t02_*` hay bảng `t02_transaction_probe`; `hr_ats` và `hr_ats_test` được giữ lại.

### Câu hỏi / việc còn lại

- #9–#12 ghi các mặc định nhỏ về health lỗi, config trước stage/auth, downgrade extension và DB trống cho test migration.
- #13 là cảnh báo deprecation thư viện, không ảnh hưởng các tiêu chí nghiệm thu; chưa thêm `httpx2` ngoài spec và không tắt cảnh báo.
- Chờ quy trình `Review T02` và merge vào `main`. Auth theo T04, mô hình nghiệp vụ theo T05, worker thật theo T07; T02 chỉ triển khai nền đã mô tả.

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
