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

T10 thêm `tests/unit/test_parse.py`, `test_cv_retention.py`,
`tests/api/test_dedupe.py`, `test_cv_pipeline.py` và mở rộng `test_cv_worker.py`
trong `uv run pytest`: ba lời gọi parse đồng thời bằng barrier, gộp output và
schema sai retry đúng một lần; tháng lịch/cuối tháng/năm nhuận/cấu hình dương;
email/SĐT/identity conflict/soft delete/tên + cosine PostgreSQL; upload 10 CV giả
theo nhãn qua HTTP → storage thật → extract thật → FakeLLM → Candidate. Cùng lô
có PDF hỏng, thêm CV khác định dạng cùng email, SHA-256 lặp và delivery lặp;
kiểm mọi bước lỗi an toàn, rollback candidate update/DB constraint, hook nghi
trùng không tự gộp, không sinh consent/application và không log/gửi liên hệ.
Test quyền file riêng sau parse không mở file khác cùng người. DB tạm qua
`empty_engine` kiểm commit trước publish, hai file khác hash cùng liên hệ, hai
delivery cùng pending ID và crash/redelivery trên kết nối PostgreSQL độc lập.
Các test upload/quyền T07 dùng kết quả extract giả rõ ràng cho fixture ảnh trắng/
PDF ngắn; test T10 dùng file PDF/DOCX thật từ bộ giả đã commit, không mock extract.
Không thay đổi migration, dependency, frontend hoặc điều kiện skip OCR của T08.

T11 thêm `tests/unit/test_anonymize.py`, `test_embed.py`, `test_reembed_cli.py`,
`tests/api/test_embeddings.py` và mở rộng `test_cv_pipeline.py` trong lệnh chuẩn
`uv run pytest`: 50 CV giả trích xuất thật cùng biến thể tên có/không dấu/NFD/hoa
thường, metadata VI/EN/nhãn riêng dòng, link/ảnh và giữ kỹ năng/lịch sử làm việc.
Factory/fake L2/tất định/đúng chiều; local qua boundary SentenceTransformer giả
kiểm cache/flags/encode/lỗi không lộ nội dung, không tải model. Pipeline kiểm chỉ
text đã ẩn danh đi vào embedder, vector đúng chiều và top-k cosine PostgreSQL;
nghi trùng không gộp, rollback revision khi embedding lỗi/sai chiều. Hook Job và
CLI reembed kiểm tạo/cập nhật, repeatable, rollback toàn lượt không trộn model,
clear vector hết hạn/đã xoá/đã gộp và lỗi CLI an toàn. Test T10 bỏ kỳ vọng hook
embedding rỗng vì T11 đã triển khai, giữ và tăng kiểm tra dữ liệu/quyền cũ.
CLI có test subprocess thật trên DB tạm đã migrate và regression trợ giúp tiếng
Việt khi stdout Windows dùng cp1252.
Dependency local là extra nên CI mặc định không import torch/tải trọng số.

T12 thêm `tests/unit/test_scoring_rules.py`, `test_score.py`,
`tests/api/test_scoring.py` và hai test cạnh tranh trong `test_cv_worker.py` vào
`uv run pytest`. Unit kiểm mọi nhánh/thứ tự ưu tiên mức AI, biên 299/300 ký tự,
50% unknown/75 điểm, trọng số/partial/cấu hình, thiếu nice/must/criteria, round;
trích dẫn bịa/null/sai hoa thường, NFC/NFD/khoảng trắng và coverage tiêu chí.
API PostgreSQL kiểm ba endpoint, admin/lead/owner/member/outsider/thu hồi quyền,
auth/CSRF/input, trùng active/soft delete, ứng viên đã gộp/hết hạn, queue/provider/
activity lỗi, rollback, bulk cô lập lỗi, giữ stage/owner và chỉ text ẩn danh vào LLM.
DB tạm với kết nối worker độc lập kiểm commit trước publish, hai insert cùng cặp,
hai score delivery chỉ một lần gọi AI/activity, crash rollback rồi delivery lại.
Luồng upload thật 50 PDF/DOCX kỹ thuật số → parse/ẩn danh/embedding → thêm vào 5
Job từ jobs.json → score FakeLLM kiểm 250 cặp; tính cả 50 cặp của 10 CV scan chưa
chạy trong mẫu số 300 để yêu cầu khớp ≥70% trên toàn ma trận; thêm kiểm tra ≥70%
trên 60 CV phải khớp cả năm Job. OCR scan vẫn được
kiểm riêng T08/Linux/CI. Không sửa dữ liệu nhãn hay công thức để tăng tỷ lệ,
không gọi provider/mạng ngoài và không thay điều kiện skip OCR.

## CI
T13 thêm `tests/api/test_jobs.py` vào `uv run pytest`: CRUD theo endpoint spec,
scope Job owner/member, admin/lead, thu hồi membership, filter/tổng/phân trang,
CSRF/auth/input, validate PATCH theo dữ liệu đã ghép, tham chiếu ngừng hoạt động,
mốc mở/đóng, vector FakeEmbedder, transaction rollback và needs_rescore không tự
publish. Vitest kiểm lỗi tiêu đề tiếng Việt/focus, lương/yêu cầu bắt buộc, lưu form
nguyên tử kèm member_ids, hỏi chấm lại/xác nhận/huỷ/retry, lỗi tải/lưu và quyền
quản lý đơn vị. Các bộ test cũ và kiểm chuỗi i18n tiếp tục chạy; không gọi mạng
ngoài hoặc đổi schema/dependency. Có thể dùng browser fixture T04 để kiểm tra
đơn vị tuyển → tạo/sửa Job với API thật trước seed nghiệp vụ T18.


GitHub Actions (`.github/workflows/ci.yml`) chạy trên mỗi push vào `main` và `task/**` và mỗi pull request: Postgres 16 + pgvector và Redis 7 dạng service, `scripts/init-db.sql`, rồi `uv sync --frozen`, ruff, mypy, `alembic upgrade head`, pytest. Task chỉ được merge khi CI xanh. Job frontend T03 dùng Node 22, chạy `npm ci`, `npm run lint` (ESLint + Prettier), `npm run typecheck`, `npm test`, `npm run build`. Vitest dùng jsdom, mock fetch tại boundary và không gọi mạng ngoài. Playwright mới được cài/cấu hình ở T03; E2E có dữ liệu bổ sung tại T18.

## Kiểm thử T14

T14 thêm `tests/api/test_ranking.py` trong `uv run pytest`: quyền owner/member/
thu hồi membership kể cả danh sách rỗng, input/phân trang/q literal/filter/sort,
thống kê đồng nhất với danh sách Job, bỏ hồ sơ đã xoá/gộp/hết hạn, snapshot file
không lộ lỗi DB hoặc trạng thái Application khác quyền. Batch 10 PDF/DOCX giả từ
bộ T06 qua storage/extract/parse/ẩn danh/embedding/score FakeLLM, kèm executable
và PDF hỏng: bảng đúng 10 dòng (3 high, 1 medium, 6 low), file lỗi riêng
và file sau vẫn hoàn tất. Kiểm log polling thành công DEBUG, lỗi INFO.

Vitest `job-detail.test.tsx` kiểm bảng sáu cột, filter, drawer/Escape/trả focus,
upload FormData/index, lỗi Việt đúng tên file, polling thật mỗi 3 giây qua ba
trạng thái, retry lỗi trạng thái riêng, trùng Job khác và giới hạn 50 file.
HTTP boundary được mock, không mạng ngoài. E2E `job-ranking.spec.ts` kéo thả
10 CV giả và hai file lỗi bằng DataTransfer trên API thật/FakeLLM, kiểm thứ tự,
filter/rỗng/drawer/counts ở 1280px; giữ E2E auth T04, tài khoản ranking riêng.

Để chạy toàn bộ E2E trước seed T18: tại backend dùng
`uv run python -m tests.ranking_browser_server`, tại frontend `npm run dev`, rồi
lệnh chuẩn `npx playwright test`. Fixture chỉ dùng PostgreSQL localhost, tạo DB
`hr_ats_test_t14_<uuid>` và storage tạm, migrate bằng Alembic, eager Celery và fake
provider, chặn request browser ngoài localhost. Tạo file `var/t14-browser.stop`
ở repo root để dừng graceful và tự dọn đúng DB/storage của lượt chạy; giữ DB dev,
DB test và volume. `tests.auth_browser_server` T04 vẫn dùng riêng cho auth E2E;
fixture T14 hỗ trợ cả ba bài. Không đổi schema, dependency hay ngoại lệ OCR.

## Kiểm thử T15

`tests/api/test_profile.py` trong `uv run pytest` kiểm detail/audit candidate.view,
DOCX text có quyền và không xuất storage/parsed/vector, upsert lần hai cùng user,
phản hồi riêng từng user, activity và rollback, whitelist sửa thông tin, ghi chú,
CSRF/auth/validation, owner/member/admin/lead/ngoài quyền/thu hồi quyền, ứng viên
đã xoá/gộp/hết hạn. Chỉ dữ liệu giả và PostgreSQL local, không gọi provider/mạng ngoài.

Vitest `candidate-profile.test.tsx` kiểm các ký hiệu tiêu chí, dịch cảnh báo,
câu insufficient, đồng ý/không đồng ý có sửa mức, form thông tin/ghi chú, tải/lỗi/
thử lại và escape nội dung. Kiểm API client đọc blob có cookie, tạo/thu hồi URL
PDF khi đóng; test toàn bộ dictionary không có thuật ngữ bị cấm. E2E mới
`candidate-profile.spec.ts` dùng API thật và DOCX/PDF giả T06, FakeLLM, kiểm
feedback lặp, sửa tên, ghi chú, mở lại dữ liệu và viewer ở 1280px. Fixture
`tests.ranking_browser_server` thêm tài khoản profile riêng để không thu hồi
phiên của các bài cũ. Lệnh chuẩn E2E, cách dừng/dọn vẫn như T14 ở trên.
Riêng bài T15 dùng channel `chromium` (browser đầy đủ cài cùng
`npx playwright install chromium`) để kiểm native PDF renderer; headless shell
mặc định không có viewer này. Guard mạng E2E cho phép localhost và URL blob
có origin localhost, vẫn chặn mọi request ngoài máy. Kiểm plugin PDF được gắn
và xem ảnh chụp trước khi kết luận viewer hoạt động.
Guard bài T15 cho phép thêm tài nguyên offline của PDF viewer tích hợp
(`chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai`, `chrome://resources`);
các URL HTTP(S) ngoài localhost vẫn bị chặn.

## Kiểm thử T16

`tests/api/test_cv_bank.py` trong lệnh chuẩn `uv run pytest` kiểm full-text không
dấu "ke toan" → "Kế toán", filter kết hợp/Unicode/literal wildcard/phân trang,
DTO không lộ liên hệ/CV/vector, thứ tự cosine thật trên PostgreSQL và lỗi adapter
an toàn (FakeEmbedder/spy, không mạng). Gợi ý loại ứng viên đã có Application
đang hoạt động, cho hồ sơ đã lưu trữ, giới hạn 50, vector null, auth/owner/member/
thu hồi quyền và eligibility của mọi mode. Nhãn nghi trùng đối xứng chỉ tóm tắt.
Gộp admin/lead, recruiter bị từ chối, CSRF/Origin/input/nguồn hoặc đích không hợp
lệ; chuyển file/hồ sơ, chỉ một Application đang hoạt động mỗi Job, giữ lịch sử/
feedback, consent/retention và rollback toàn bộ nếu activity lỗi.

`test_cv_worker.py` thêm test T16 trên DB tạm đã migrate, hai kết nối PostgreSQL
độc lập điều khiển bằng Event: request create đã đọc source, merge commit rồi
create tiếp tục phải từ chối source vừa gộp. Không ngủ chờ thời gian hoặc gọi
provider thật, tái sử dụng fixture `committed_runtime`.

Vitest `cv-bank.test.tsx` kiểm filter/tìm theo nghĩa, thẻ Việt, lựa chọn Job,
so sánh/cancel/chọn đích/gộp/lỗi retry, recruiter không có nút gộp, thêm nhiều
người có 409/503/score failed và retry chỉ người lỗi, trạng thái rỗng/thử lại.
Nhãn select liên kết htmlFor/id để trình duyệt và screen reader nhận đúng.

E2E `cv-bank.spec.ts` dùng fixture `uv run python -m tests.ranking_browser_server`
như T14/T15 (thêm tài khoản bank riêng và hai CV DOCX giả/hint trong DB/storage
dùng một lần), chạy frontend rồi lệnh chuẩn `npx playwright test`. Luồng thật:
tìm không dấu, bật tìm theo nghĩa, chọn hai người từ kho vào Job, chọn nhiều gợi
ý từ Job khác, mở lại không thấy người đã thêm; xác nhận gộp và kiểm cả hai Job
chỉ còn một hồ sơ. Chụp thẻ/hộp ở 1280px, kiểm overflow và lỗi JS. Browser chặn
request ngoài localhost; không thêm seed production hoặc thay phạm vi T18.
Dừng/dọn fixture bằng `var/t14-browser.stop` như trước. Khi kiểm production
build, chạy `npm run build` sau khi dừng dev rồi `npm run start`; không chạy
build và dev đồng thời vì chúng cùng ghi `.next`.

## Kiểm thử T17

`tests/api/test_export.py` kiểm quyền Job, workbook mở được bằng openpyxl, tiêu
đề/cột tiếng Việt, số dòng, thứ tự/xuất trường, chuỗi chống công thức và audit
`candidate.export` chỉ có record_count/job_id. Chạy qua `uv run pytest`, fixture
PostgreSQL local và dữ liệu giả; không ghi workbook hay PII vào repo/log.
Vitest `job-detail.test.tsx` kiểm dialog cảnh báo dữ liệu cá nhân, gọi API dạng
blob, tên file và thao tác tải; không gọi mạng ngoài.

## Kiểm thử T18

`tests/unit/test_seed.py` kiểm seed từ chối prod, DB ngoài localhost, provider
thật và storage từ xa trước khi mở DB, lỗi CLI không lộ nội dung exception,
và khôi phục cấu hình eager dù có lỗi. `tests/api/test_seed_demo.py` migrate DB
tạm trống rồi chạy CLI seed thật hai lần bằng subprocess (APP_ENV=dev, fake,
storage tạm): 4 user/3 đơn vị/5 Job/40 ứng viên/40 file/40 hồ sơ đã chấm,
embedding và provenance, consent vẫn null, không tăng bản ghi/file hay chấm lại,
giữ stage HR đã sửa. Kiểm thêm không ghi đè tài khoản và phục hồi seed sau lỗi
pipeline. Tất cả chạy trong `uv run pytest`, không provider/mạng ngoài.
Test FakeLLM bổ sung danh sách kỹ năng có tiêu đề riêng dòng của CV giả T06;
giữ test không suy đoán thông tin và không nuốt mục sau khi thiếu giá trị.

Theo README **Demo nhanh**, migrate → `uv run python -m app.scripts.seed` →
API + worker Celery thật (Windows `-P solo`) + web, rồi tại frontend chạy
`npx playwright test m1-smoke.spec.ts`. Seed chạy các task đồng bộ để CLI chỉ
thành công sau pipeline; upload mới từ web dùng worker/Redis thông thường.
Smoke đăng nhập recruiter, tạo Job kế toán từ jobs.json bằng form, kéo 5 file
giả dành riêng, đợi done, đối chiếu mức/thứ tự với nhãn, mở drawer và sửa phản
hồi, mở lại kiểm lưu, tìm kỹ năng bookkeeping và xác nhận kết quả thuộc batch
vừa upload. Test chỉ thêm ZIP/PDF comment vào payload để chạy lại trên dev DB
mà không đổi file gốc hoặc nội dung CV. Browser chặn mạng ngoài localhost.

Lệnh E2E đầy đủ vẫn là `npx playwright test`, dùng
`uv run python -m tests.ranking_browser_server` và web như T14–T16. Fixture
thêm catalog user/đơn vị/Job T18, không nhập 40 CV seed vào DB fixture để tránh
đụng các file gốc của bài cũ. Luồng smoke dùng 5 file khác các bài cũ, tài khoản
recruiter riêng; không thu hồi phiên hoặc sửa dữ liệu test khác. DB seed thật
được kiểm riêng bằng CLI trên DB trống và demo với worker thật. Không thêm
schema, dependency, thay điều kiện skip OCR hoặc tự seed khi khởi động app.

## Kiểm thử T19

`tests/api/test_pipeline.py` trong `uv run pytest` kiểm đủ 64 cặp stage bằng
ma trận kỳ vọng độc lập từ spec, undo mọi cặp move hợp lệ, giữ event gốc và
ghi event/activity đảo chiều. Kiểm sáu lý do chuẩn, validation/note/input thừa,
biên 24 giờ ±1 microsecond/đúng biên/mốc tương lai, actor recruiter khác bị từ
chối và quyền override lead/admin. Chỉ undo event mới nhất một lần, lịch sử
khởi tạo/thiếu/sai/đã xoá không được undo; move mới có lượt undo mới.

API PostgreSQL kiểm đủ tám cột kể cả rỗng, thứ tự/thông tin card tối thiểu,
owner/member/thu hồi quyền/owner Application riêng, auth/CSRF/Origin, hồ sơ
đã xoá/gộp/hết hạn, lỗi activity rollback cả stage/timestamp/reason/event và
note không lọt log. Hai session DB tạm đã migrate, đồng bộ bằng Barrier,
kiểm hai move/undo trùng chỉ thành công một lượt và đọc lại identity map sau
khi chờ lock. `test_system.py` kiểm đầy đủ nhãn config, gồm HIRING_UNIT_LABEL
tuỳ chỉnh. Không gọi AI/mạng ngoài/gửi email hoặc thêm migration/dependency/UI.
Test hồi quy dùng UUID gây lỗi #71 ở cv_file_id/stage_event_id/undo_of và
giữ các kiểm tra từ chối SĐT/email/khoá nhạy cảm/UUID nối thêm PII. Bộ
core_data cũ tiếp tục kiểm payload metadata và transaction, không đổi fixture
hoặc nới assertion để tránh UUID ngẫu nhiên.

## Definition of Done cho mỗi task

1. Đáp ứng toàn bộ tiêu chí nghiệm thu trong file task.
2. Có test cho logic mới (unit cho services/ai, API test cho endpoint); test cũ vẫn pass.
3. Lint và typecheck sạch.
4. Có migration Alembic nếu đổi schema; `alembic upgrade head` chạy được trên DB trống.
5. Không có PII thật trong code, test, log, fixture.
6. Chuỗi giao diện mới nằm trong `vi.ts`.
7. Nếu thay đổi hợp đồng (API, schema, KPI) thì cập nhật spec tương ứng trong cùng commit.
8. Cuối task, ghi tóm tắt vào `tasks/PROGRESS.md`: task id, việc đã làm, file chính, lệnh test đã chạy và kết quả, việc còn lại / câu hỏi.
