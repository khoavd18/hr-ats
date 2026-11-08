# 08 · Kiểm thử và Definition of Done

## Lệnh chuẩn (agent dùng đúng các lệnh này)
| Việc | Lệnh |
|---|---|
| Hạ tầng dev | `docker compose up -d db redis mailpit` |
| Cài backend | `cd backend && uv sync` |
| Migration | `cd backend && uv run alembic upgrade head` |
| Chạy API | `cd backend && uv run uvicorn app.main:app --reload` |
| Chạy worker | `cd backend && uv run celery -A app.workers.celery_app worker -Q ai,email,default -l info` (Windows thêm `-P solo`) |
| Test backend | `cd backend && uv run pytest` |
| Lint backend | `cd backend && uv run ruff check . && uv run ruff format --check .` |
| Typecheck backend | `cd backend && uv run mypy app` |
| Seed dev | `cd backend && uv run python -m app.scripts.seed` |
| Cài frontend | `cd frontend && npm ci` |
| Chạy frontend | `cd frontend && npm run dev` |
| Test frontend | `cd frontend && npm test` |
| Lint frontend | `cd frontend && npm run lint && npm run typecheck` |
| E2E | `cd frontend && npx playwright test` (cần API + web + seed) |
| Đánh giá AI | `cd backend && uv run python ../eval/run_score_eval.py --provider fake` |

Test backend chạy trên DB Postgres riêng (`hr_ats_test`, tạo bởi fixture), Celery chạy ở chế độ eager, `LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake`, email gửi vào bộ nhớ. **Test không được gọi mạng ra ngoài.**

Nền T02: fixture chỉ cho phép DB trên localhost và luôn chọn `hr_ats_test`, dùng transaction ngoài + savepoint để rollback cả khi code gọi `session.commit()`. Test migration từ DB trống dùng DB tạm có tên `hr_ats_test_t02_<uuid>` trên cùng server, chỉ xoá đúng DB do fixture vừa tạo. DB dev và `hr_ats_test` được giữ lại. Migration đầu chỉ bật extension `vector`/`unaccent`; downgrade giữ extension vì chúng có thể do hạ tầng T01 tạo trước Alembic.

Schema test chỉ được tạo/cập nhật bằng Alembic, không dùng `Base.metadata.create_all`. Test đối chiếu `Base.metadata` với schema đã migrate bằng `compare_metadata` (gồm type và server default); thiếu table/column/index phải bị phát hiện. Fixture giữ DB giữa các phiên; khi sửa migration đã áp dụng trong dev, cần reset riêng `hr_ats_test` theo hướng dẫn README để chạy lại lịch sử. Migration đã merge phải được thay đổi bằng revision mới.

T04 bổ sung API test auth/users, bảng quyền, CLI, đăng nhập sai đồng thời và refresh token cạnh tranh; tất cả dùng dữ liệu giả. `uv run python -m tests.auth_browser_server` tại backend tạo DB tạm `hr_ats_test_t04_<uuid>` riêng, migrate/seed user giả và phục vụ API localhost:8000. Chạy `npm run dev` rồi lệnh chuẩn `npx playwright test` tại frontend để kiểm tra auth UI với backend thật (không cần seed T18). Dừng server bằng Ctrl+C để xoá đúng DB tạm của fixture. Các test này không thay thế E2E nghiệp vụ tại T18; xem README về điều kiện chạy. Vitest kiểm tra route guard và refresh client, Playwright chặn request ngoài localhost.

T05 bổ sung integration PostgreSQL cho 10 bảng lõi/schema đọc, unique application chỉ khi chưa xoá, FK/unique/CHECK, trigger full-text không dấu khi insert/update, cosine top-k và kiểm tra planner có thể dùng GIN/HNSW. Test ma trận quyền Job dùng owner/member thật trong DB, gồm thu hồi membership, soft delete và dữ liệu owner chưa flush. Test migration kiểm tra upgrade → downgrade base → upgrade, không sót bảng/enum/function; thêm DB trống với EMBEDDING_DIM=8. Không dùng dữ liệu hay gọi provider bên ngoài; kiểm tra index trên dữ liệu nhỏ chỉ chứng minh khả năng dùng index, chưa phải benchmark quy mô production.

T06 bổ sung `tests/unit/test_synthetic_cvs.py` vào lệnh chuẩn `uv run pytest`: validate schema/cặp file/ma trận Job, liên hệ và công ty giả, độ phủ bố cục/nghề, dung lượng, nội dung PDF/DOCX và scan ảnh; sinh lại để so SHA-256 mọi file với bộ 60 CV đã commit. Test không cần DB/Redis hay provider, vẫn dùng chặn mạng ngoài của fixture chung. Lint script ngoài backend bằng `uv run ruff check ../eval` và `uv run ruff format --check ../eval` tại `backend/` (cũng chạy trong CI). Mypy chuẩn vẫn là `uv run mypy app`; T06 không đổi schema DB/API/UI. Hướng dẫn sinh và contract fixture: `eval/README.md`.

T07 bổ sung test local storage và S3 qua `botocore.stub.Stubber` (không gọi S3/MinIO thật), magic bytes/macro/ZIP và giới hạn file, cấu hình ba queue/eager JSON. API test PostgreSQL upload hỗn hợp 3 hợp lệ + executable đổi đuôi, SHA-256 chống trùng, quyền owner/member/uploader/admin/lead, thu hồi membership, soft delete, audit, CSRF, lỗi storage/queue và retry. Test Celery eager dùng session test được inject; một test concurrency tạo DB tạm riêng qua fixture `empty_engine`, chạy hai upload đồng thời và worker với kết nối DB độc lập để chứng minh commit trước publish, một record/object/activity. Tất cả nằm trong `uv run pytest`; không đổi migration/schema hay frontend. Celery dev có thể smoke bằng lệnh worker chuẩn ở trên (Windows `-P solo`).

T08 bổ sung `tests/unit/test_extract.py` và `test_redact.py` vào lệnh chuẩn
`uv run pytest`: so nội dung 50 CV kỹ thuật số với nhãn, thứ tự hai cột và kỹ năng
DOCX bảng, thứ tự bảng lồng/header/footer/ô merge, NFC; PDF 49/50 ký tự, PDF hỗn hợp,
300 DPI, ảnh PNG/JPEG, alpha/EXIF và các lỗi an toàn. Kiểm thử redaction gồm trên
12 dạng SĐT/email, chuẩn hoá `+84`, bỏ trùng, giữ ngày/phiên bản, không nối số qua
xuống dòng. Test OCR thật trên 10 PDF scan trong `data/sample_cvs/` và ảnh PNG/JPEG
của một scan chỉ skip khi thiếu executable Tesseract theo ngoại lệ rõ trong T08.
CI cài `tesseract-ocr` và `tesseract-ocr-vie` (kèm `eng`) trước pytest để thực thi
các test này. Tất cả OCR chạy local; test thiếu OCR/timeout/lỗi mock subprocess,
không gọi mạng ngoài. Không thêm dependency Python, schema DB hoặc UI ở T08.

T09 thêm `tests/unit/test_ai_schemas.py`, `test_prompts.py`, `test_llm.py` trong
`uv run pytest`: factory/environment, FakeLLM với prompt thật, schema/ngày/enum/
lý do/bằng chứng, version/Jinja2/JSON phân định dữ liệu không đáng tin cậy. HTTPX
MockTransport kiểm contract ba provider, auth/timeout/token, sửa JSON một lần,
retry/backoff mạng/429/5xx có giới hạn, 4xx/redirect/envelope/refusal/truncated và
log không có input/output/key giả kể cả chưa có filter. CLI smoke test bằng fake
và Anthropic HTTP mock; provider thật chỉ chạy thủ công theo README. Không gọi
mạng ngoài/key thật; không đổi schema DB/API/UI.

## CI

GitHub Actions (`.github/workflows/ci.yml`) chạy trên mỗi push vào `main` và `task/**` và mỗi pull request: Postgres 16 + pgvector và Redis 7 dạng service, `scripts/init-db.sql`, rồi `uv sync --frozen`, ruff, mypy, `alembic upgrade head`, pytest. Task chỉ được merge khi CI xanh. Job frontend T03 dùng Node 22, chạy `npm ci`, `npm run lint` (ESLint + Prettier), `npm run typecheck`, `npm test`, `npm run build`. Vitest dùng jsdom, mock fetch tại boundary và không gọi mạng ngoài. Playwright mới được cài/cấu hình ở T03; E2E có dữ liệu bổ sung tại T18.

## Definition of Done cho mỗi task
1. Đáp ứng toàn bộ tiêu chí nghiệm thu trong file task.
2. Có test cho logic mới (unit cho services/ai, API test cho endpoint); test cũ vẫn pass.
3. Lint và typecheck sạch.
4. Có migration Alembic nếu đổi schema; `alembic upgrade head` chạy được trên DB trống.
5. Không có PII thật trong code, test, log, fixture.
6. Chuỗi giao diện mới nằm trong `vi.ts`.
7. Nếu thay đổi hợp đồng (API, schema, KPI) thì cập nhật spec tương ứng trong cùng commit.
8. Cuối task, ghi tóm tắt vào `tasks/PROGRESS.md`: task id, việc đã làm, file chính, lệnh test đã chạy và kết quả, việc còn lại / câu hỏi.
