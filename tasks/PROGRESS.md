# Tiến độ

| ID | Trạng thái | Ngày | Ghi chú |
|---|---|---|---|
| T01 | done | 2026-11-08 | Ba tiêu chí nghiệm thu đạt. MinIO (profile `s3`, tuỳ chọn) hoãn lại vì image không tải được; dùng `STORAGE_BACKEND=local`. Xem câu hỏi #8. |
| T02 | done | 2026-11-08 | Review lần 2: APPROVE WITH NITS, 76 test pass trên Postgres/Redis thật (tasks/reviews/T02.md). Nhắc việc N1→T05, N2→T14, N3→T26. |
| T03 | done | 2026-11-08 | VERIFIED: khung frontend Next.js 15, sáu trang tiếng Việt, API client và bộ component; 39 test pass, lint/typecheck/build sạch, smoke Chromium 1280px đạt. Chờ review và merge. |
| T04 | done | 2026-11-08 | VERIFIED: auth cookie JWT/CSRF, Argon2id, khoá đăng nhập, CLI admin và quản lý người dùng; 152 test backend, 47 test frontend, 2 E2E pass. Chờ Review T04 và merge. |
| T05 | done | 2026-11-08 | VERIFIED: 10 bảng lõi, migration/rollback, full-text không dấu, HNSW cosine, schema đọc, quyền DB owner/member, activity và che PII. 225 test backend pass; Ruff/mypy sạch. Chờ Review T05 và merge. |
| T06 | done | 2026-11-08 | VERIFIED: bộ sinh offline theo seed, 60 CV giả/60 nhãn, 5 Job/300 nhãn phù hợp, 6 nghề/6 bố cục; 9,76 MB. Backend 248 test pass, Ruff/mypy sạch; 22 test dữ liệu pass trên Linux, byte khớp Windows. Chờ Review T06 và merge. |
| T07 | review | 2026-11-08 | VERIFIED: storage local/S3, upload theo lô/chống trùng, quyền đọc/download/audit, ba queue Celery và worker tạm. 298 test backend pass (50 test T07), Ruff/mypy sạch; chờ Review T07, CI và merge. |
| T08–T33 | todo | | |

## Nhật ký
<!-- Agent thêm mục mới ở đầu: ## Txx · YYYY-MM-DD · done|blocked, rồi tóm tắt -->

## T07 · 2026-11-08 · review

VERIFIED: triển khai T07 theo `tasks/_implement.md` trên nhánh `task/T07-storage-upload-celery`; T05 đã `done`, working tree sạch trước khi bắt đầu. Giữ trạng thái `review` đến khi được duyệt và merge vào main.

- Thêm interface `Storage`, LocalStorage và S3Storage (boto3). Key UUID hex ngẫu nhiên không chứa tên gốc; local chặn traversal/symlink và tạo file riêng, S3 không cấp public URL. S3 có timeout/retry hữu hạn, đóng stream đọc, lỗi storage chung không lộ path/credential/provider. Thêm đúng dependency boto3 theo task cùng lockfile; metadata license mới là Apache-2.0/MIT.
- API multipart nhận 1–50 file, tối đa 10 MiB/file; magic bytes PDF/DOCX/JPEG/PNG, kiểm content type Word/macro/VBA, từ chối ZIP mã hoá/traversal/trùng entry/quá giới hạn giải nén. Trả kết quả từng index và lỗi tiếng Việt riêng, không phản chiếu tên/nội dung file lỗi. Tên gốc chỉ là metadata đã bỏ path/control; storage/header tải về dùng UUID.
- SHA-256 unique và advisory transaction lock chống trùng cả khi upload đồng thời. Kiểm quyền bản ghi cũ trước trả duplicate; không đổi uploader/Job, không thêm object/activity/task, không phục hồi soft delete. File mới và activity `cv_uploaded` commit chung, cleanup object mới khi transaction lỗi. Không tạo Candidate/Application, parse hay chấm điểm trong T07.
- GET trạng thái/download kiểm quyền ở service qua `authorize`; recruiter theo Job upload hoặc application còn hiệu lực, file chưa gắn Job/Candidate chỉ uploader/admin/lead. Thu hồi membership không bị uploader vượt quyền. Soft delete file/ứng viên trả 404, thiếu quyền trả 403; không trả storage key, text, parsed JSON hay lỗi provider. Audit `view`/`download` chỉ định danh/IP kết nối hợp lệ; download commit audit sau đọc storage, trước trả byte. Attachment tên UUID, nosniff và no-store.
- Celery có ba exchange/routing key riêng `ai`, `email`, `default`, JSON-only; test eager/memory, dev/prod Redis. Publish sau commit, task chỉ nhận UUID và dùng session riêng để đổi pending → done idempotent. Lỗi publish đặt failed bằng UPDATE có điều kiện, không ghi đè done; upload lại cùng file retry được lỗi publish này, giữ ID/activity. Worker dùng logging PII chung. Smoke phát hiện binding mặc định chung; đã sửa và bổ sung test gửi thông điệp thật qua memory broker để chứng minh AI chỉ tới queue ai.
- Cập nhật README, spec 01/03/07/08, mặc định #30–#33. Không đổi schema DB/KPI/UI, migration head vẫn `0003_core_data_model`; không sửa skill thư viện, không thêm service, không gửi email hay gọi AI/provider bên ngoài.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Upload 3 file hợp lệ + executable đổi đuôi PDF → 3 tạo, 1 lỗi tiếng Việt | VERIFIED — đạt | `test_mixed_upload_duplicate_status_download_and_audit`: PDF/DOCX/PNG giả hợp lệ, MZ giả bị từ chối; ba snapshot pending, GET eager done, đúng ba activity/object/record. Có test JPEG, 10 MiB, 50/51 file, DOCM và macro đổi đuôi |
| Upload lại cùng file không tạo bản ghi mới | VERIFIED — đạt | Test mixed upload kiểm cùng ID, ba record/object/activity sau upload lại; `test_concurrent_upload_publishes_after_commit_and_worker_uses_own_connection` chạy hai upload đồng thời trên DB tạm, một record/object/activity, worker kết nối riêng thấy record đã commit |
| Recruiter không có quyền download → 403 | VERIFIED — đạt | `test_unauthorized_recruiter_cannot_read_download_or_probe_duplicate`, test thu hồi membership/uploader/owner, quyền Candidate qua Application và soft delete; duplicate không lộ ID/metadata |
| Audit có bản ghi download | VERIFIED — đạt | Test mixed upload đối chiếu action/entity/file/actor cho cả ba download; lỗi storage/không có quyền không ghi audit download; GET metadata có audit view |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, dùng dịch vụ local có sẵn, giữ volume/dữ liệu dev.
- `uv sync`: pass, 74 package resolve/73 package kiểm tra. `uv run alembic upgrade head`: pass; `uv run alembic current`: `0003_core_data_model (head)`. Test migration DB trống/rollback cũ vẫn pass.
- `uv run pytest`: lượt chốt **298 passed, 1 warning**, không skip; gồm **50 test T07** và toàn bộ 248 test cũ. PostgreSQL localhost thật, Celery eager/memory; S3 Stubber và bộ chặn mạng ngoài của fixture chung. Các lượt theo phần: 29 test storage/validation, 44 rồi 47 test T07; sau sửa binding, 50 test T07 pass và full suite chạy lại pass.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 78 file đã format. `uv run mypy app`: pass, 48 source file. `uv run ruff check ../eval`, `uv run ruff format --check ../eval`: pass, 4 file.
- Với `APP_ENV=test`, `uv run celery -A app.workers.celery_app worker -Q ai,email,default -l info -P solo`: worker ready, đăng ký `process_cv_file`, ba binding riêng ai/ai, email/email, default/default. Dừng bằng Ctrl+C sau smoke; không đọc queue dev, không gọi provider. Đây là smoke memory; chưa kiểm worker Redis bằng subprocess.
- `git diff --check`: sạch. Tự review theo secure-code-review: quyền/CSRF ở cả endpoint và service, duplicate có kiểm quyền, file không public, log không có CV/tên gốc/PII, lỗi không lộ provider; sửa race trạng thái publish và binding queue, có test hồi quy. Không còn finding đã xác nhận chưa xử lý. Kiểm metadata license của năm package mới: Apache-2.0/MIT; `pip-audit` chưa có trong môi trường nên không khẳng định đã quét lỗ hổng dependency.

File chính: `backend/app/{storage/*,workers/*,api/cv_files.py,services/cv_files.py,services/cv_validation.py,schemas/cv_files.py,core/permissions.py,main.py}`, `backend/tests/{api/test_cv_files.py,api/test_cv_worker.py,unit/test_storage.py,unit/test_cv_validation.py,unit/test_celery_app.py,cv_helpers.py}`, manifest/lockfile, README, spec và PROGRESS.

ASSUMED: mặc định #30–#33 đã ghi rõ, không có blocker. NOT TESTED: CI remote (chưa push), review độc lập, S3/MinIO runtime (hoãn theo quyết định #8), worker Redis trong process thật, benchmark production và automated dependency vulnerability audit. Frontend/E2E không bị ảnh hưởng nên không chạy lại. Khoảng crash giữa commit DB và publish chưa có outbox/reconciliation trong phạm vi T07; xem #33 trước production. Pipeline CV thật thuộc T10. Chờ `Review T07`, CI xanh và merge; chưa chuyển sang `done`.

## T06 · 2026-11-08 · review

VERIFIED: triển khai đúng phạm vi T06 theo `tasks/_implement.md` trên nhánh `task/T06-synthetic-vietnamese-cvs`; T01 đã `done`, working tree sạch trước khi bắt đầu. Hoàn thành triển khai, giữ trạng thái `review` đến khi được duyệt và merge vào main.

- Bộ sinh `eval/generate_synthetic_cvs.py` chạy offline qua uv, có `--count`, `--seed`, `--out`. Nguồn giả gồm tên nam/nữ trong ba nhóm vùng miền, trường/công ty ghi rõ Mô phỏng/Giả lập, sáu nhóm nghề backend/frontend/kế toán/kinh doanh/marketing/nhân sự. Email chỉ `@example.com`, SĐT mẫu `09xx 000 xxx`; không lấy dữ liệu người thật, gọi provider hay ghi trường CV/liên hệ vào log.
- Sinh sẵn **60 CV** (35 PDF, 25 DOCX), mỗi bố cục 10 CV: một cột, hai cột, bảng, khối màu đại diện giả, tiếng Anh, PDF scan chỉ có ảnh với xoay nhẹ/nhiễu có seed. Tổng `data/sample_cvs/` **9.762.667 byte**, dưới 30 MB. Tên/trường/liên hệ/kỹ năng/kinh nghiệm/học vấn trong tài liệu số được test đối chiếu với nhãn.
- Contract fixture version 1 trong `eval/schemas.py`: 60 file `<id>.json` đủ dữ liệu parse, năm Job trong `jobs.json` và **300** nhãn `expected_level`; ma trận ở jobs và từng CV khớp nhau. Nhãn gồm 270 low, 15 medium, 15 high. Giữ schema parse production/quy tắc scoring ở các task sau; các kịch bản nhãn giả chưa phải nhãn chuyên gia HR.
- Metadata/ngày tham chiếu/random cố định, ZIP DOCX chuẩn hoá timestamp/thứ tự entry. Commit Noto Sans chính thức kèm OFL; PDF nhúng toàn bộ font và khối ảnh DOCX dùng BMP để giữ byte giữa Windows/Linux. Thư mục output có dữ liệu không khớp bị từ chối, không tự xoá file cũ. CLI lỗi schema dùng thông báo chung để không phản chiếu input.
- Thêm đúng ba dependency theo T06: python-docx, PyMuPDF, Pillow (lxml phụ thuộc của python-docx), cập nhật uv.lock; pytest import được package eval ở gốc repo. CI lint cả eval ngoài backend. Hướng dẫn tại eval/README.md và README; cập nhật contract fixture/spec kiểm thử ở spec 04/08 và mặc định #27–#29. Không đổi DB/API/UI/KPI hoặc skill thư viện.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Cùng seed cho kết quả giống hệt | VERIFIED — đạt | `test_same_seed_reproduces_every_committed_byte` so SHA-256 **121 file** sau sinh lại với fixture; seed 17 sinh hai thư mục khớp byte cả DOCX/scan, đổi seed 18 đổi kết quả. 22 test dữ liệu trên Linux cũng pass với chính fixture Windows và cùng uv.lock. CLI qua uv sinh bộ riêng ở var/ được so SHA-256: 121 file, 0 lệch |
| Mọi email @example.com; không có công ty thật nổi tiếng | VERIFIED — đạt | Test validate cả 60 nhãn, email/phone duy nhất, phone đúng mẫu; tất cả employer thuộc danh sách cố định sáu tên `Công ty Giả lập ...`. Test đọc lại nội dung 50 CV số xác nhận các trường liên hệ/công ty trong tài liệu khớp nhãn |
| Mỗi CV có nhãn tương ứng, nhãn hợp lệ theo schema | VERIFIED — đạt | `test_committed_cvs_have_valid_matching_labels_and_complete_job_matrix`: đủ 60 cặp CV/JSON, đúng năm Job và 300 nhãn hợp lệ/khớp; test schema từ chối giá trị sai, file ID sai, trường thừa, matrix thiếu hoặc Job trùng. `uv run pytest`: **248 passed**, gồm **23** test T06 |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass; giữ nguyên dịch vụ/volume dev có sẵn.
- `uv sync`: pass, 69 package resolve/68 package kiểm tra, manifest/lockfile đồng bộ.
- `uv run alembic upgrade head`: pass trên DB local, giữ head `0003_core_data_model`; T06 không có migration mới. Suite kiểm chứng migration DB trống/rollback và schema cũ vẫn pass.
- `uv run python ../eval/generate_synthetic_cvs.py --count 60 --seed 20261108 --out ../var/t06-cli-samples`: pass tại backend; đối chiếu SHA-256 với data/sample_cvs: **121 file, 0 khác biệt**. Bộ commit được sinh bằng cùng script/count/seed vào data/sample_cvs.
- `uv run pytest`: lượt cuối **248 passed, 1 warning**, không skip; PostgreSQL/Redis localhost thật cho test cũ, T06 dùng file giả cục bộ và chặn mạng ngoài. Warning upstream Starlette/httpx được giữ nguyên.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 61 file đã format. `uv run ruff check ../eval`, `uv run ruff format --check ../eval`: pass, 4 file đã format. `uv run mypy app`: pass, 37 file.
- Linux: `docker run --rm` dùng image `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` (digest `sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58`), repo mount chỉ đọc, venv/cache trong /tmp; `uv sync --frozen` chuẩn bị dependency, sau đó `uv run --offline pytest tests/unit/test_synthetic_cvs.py -q`: **22 passed, 1 warning**, gồm so byte mọi fixture với Windows. Lượt này trước khi thêm test lỗi CLI cuối; thay đổi lỗi CLI không đổi byte CV/JSON.
- Lượt đầu 20/22 test pass: test đọc text phát hiện font CJK thiếu glyph tiếng Việt và scan bị thiếu nét; sửa bằng Noto Sans có giấy phép, không giảm test. Đối chiếu Linux đầu phát hiện 30 file khác byte do tag font subset và nén PNG của Pillow; sửa nhúng font đầy đủ/BMP, sau đó toàn bộ 22 test dữ liệu Linux pass. Một lần chuẩn bị Linux lỗi rename cache trên mount Windows; chuyển cache vào /tmp thành công. Test hồi quy lỗi CLI ban đầu tái hiện input bị phản chiếu; thêm xử lý ValidationError chung, lượt cuối 248 test pass.
- `git diff --check`: sạch. Kiểm UTF-8 không BOM/LF/newline cuối cho 65 file code/test/doc/JSON trọng tâm: pass. Kiểm bổ sung nguồn employer/email trên 60 nhãn: pass. Quan sát bản render PDF hai cột/bảng/scan sau sửa font: đọc được tiếng Việt, scan có nghiêng/nhiễu.
- Tự review diff: đúng scope T06, toàn bộ CV/liên hệ/employer là dữ liệu sinh giả, font kèm license, không secret/dữ liệu thật/provider hay thay đổi test cũ để giảm tiêu chí; thông báo CLI không phản chiếu CV. Không còn finding đã xác nhận chưa xử lý.

File chính: `eval/generate_synthetic_cvs.py`, `eval/schemas.py`, `eval/README.md`, `eval/assets/{NotoSans-Regular.ttf,OFL.txt}`, `data/sample_cvs/*`, `backend/tests/unit/test_synthetic_cvs.py`, `backend/{pyproject.toml,uv.lock}`, `.github/workflows/ci.yml`, README, spec 04/08, open-questions và PROGRESS.

ASSUMED: mặc định nhỏ #27–#29 đã ghi rõ; không có blocker. NOT TESTED: CI remote (chưa push), review độc lập, OCR thật (T08), bộ đánh giá AI production (T31), nhãn chuyên gia, hình thức DOCX giữa các trình đọc và khả năng giữ byte sau nâng dependency/nền tảng khác. Frontend/E2E không bị ảnh hưởng nên không chạy lại. Chờ `Review T06`, CI xanh và merge; chưa chuyển task sang `done`.

## T05 · 2026-11-08 · review

VERIFIED: thực hiện đúng T05 theo `tasks/_implement.md` trên nhánh `task/T05-core-data-model`; T04 đã `done`, working tree sạch trước khi bắt đầu. Hoàn thành triển khai, giữ trạng thái `review` cho đến khi được duyệt và merge vào main.

- Enum/model và revision mới `0003_core_data_model` cho đúng 10 bảng: hiring_units, jobs, job_members, candidates, cv_files, applications, stage_events, activities, ai_feedback, audit_log. Tái sử dụng users T04; không sửa migration đã merge, không thêm dependency/service hay endpoint. UUID v4, timestamp UTC, JSONB, FK không cascade xoá cứng, soft delete các bảng dữ liệu ứng viên và ràng buộc/index theo spec 02.
- Cả jobs/candidates dùng vector(EMBEDDING_DIM), cấu hình dimension phải dương. Trigger cập nhật search_tsv bằng simple + public.unaccent từ tên/chức danh/kỹ năng, kể cả khi sửa trực tiếp search_tsv; GIN full-text, HNSW vector_cosine_ops. Không khai báo IMMUTABLE giả cho unaccent. Unique application chỉ áp dụng khi deleted_at IS NULL; feedback và membership có unique key phục vụ upsert/chống trùng.
- Schema đọc cho 10 bảng, không xuất storage_key, text/parsed_json CV, embedding/search_tsv hay lỗi parse thô. Schema audit IP dùng kiểu địa chỉ IP tương thích đối tượng PostgreSQL trả về; serialize JSON thành chuỗi.
- authorize() nhận Job/Candidate/Application và session, truy vấn ownership/membership theo ID từ DB. Recruiter chỉ truy cập ứng viên qua application chưa xoá ở Job được phép; application.owner_id không tự cấp quyền Job. Thu hồi membership có hiệu lực ở lần kiểm tiếp; không autoflush owner chưa lưu khi kiểm quyền. Giữ ma trận admin/lead, kho CV chung và ResourceScope nội bộ T04.
- log_activity() add/flush trong transaction của caller, không tự commit; actor null cho hệ thống. Sao chép payload, từ chối khoá CV/PII và JSON không hợp lệ, không phản chiếu input. Caller phải kiểm quyền và không sao chép CV vào trường tự do.
- Hoàn thành nhắc việc review T02 N1: logging che full_name/name/candidate_name/address/phone_number/date_of_birth, gồm hậu tố, hoa/thường, gạch ngang, mapping lồng nhau/JSON/extra/key=value; vẫn giữ metadata chẩn đoán.
- Cập nhật spec 02/07/08, câu hỏi #22–#26 và README: null/default/soft delete, contract helper/schema, quyền theo DB, rollout/rollback và trình tự đổi dimension. Không sửa UI/KPI hay các task sau.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| alembic upgrade head và downgrade base chạy được | VERIFIED — đạt | Test migration upgrade → downgrade base → upgrade trên DB trống, kiểm không sót bảng/enum/function và giữ extension; CLI thật `uv run alembic upgrade head`, `uv run alembic downgrade base`, `uv run alembic upgrade head` cũng pass trên DB tạm riêng; dimension=8 cho cả hai vector được kiểm riêng |
| Tạo bản ghi mỗi bảng; unique application; full-text không dấu; vector top-k; recruiter không có quyền Job bị từ chối | VERIFIED — đạt | `uv run pytest`: **225 passed**, gồm 60 test mới trong test_core_data.py: đủ 10 bảng/schema đọc; duplicate active bị từ chối, soft delete cho phép tạo lại và restore trùng bị chặn; nguyen khớp Nguyễn, update xoá token cũ; cosine top-2 đúng thứ tự; EXPLAIN dùng được GIN/HNSW; 36 ô role/relation/action trên DB và test quyền ứng viên/thu hồi/soft delete |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, ba dịch vụ local sẵn có đang chạy; không xoá volume/dữ liệu dev.
- `uv sync`: pass, 65 package resolve/64 package kiểm tra; không thay đổi manifest/lockfile.
- `uv run alembic upgrade head`: pass trên DB dev, head `0003_core_data_model`.
- `uv run pytest`: **225 passed, 1 warning**, không skip; PostgreSQL/Redis thật trên localhost, fixture transaction rollback, provider AI giả, chặn mạng ngoài. Test schema so sánh model với migration vẫn pass.
- Lượt test theo phần đầu tiên: 151 pass, hai lỗi ở schema đọc IP và test truyền extra.name (khóa dự trữ của Python logging). Đã sửa schema IP và kiểm name ở các log shape Python cho phép; toàn bộ suite trên đã pass sau sửa, không giảm tiêu chí/skip test.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 60 file đúng định dạng. `uv run mypy app`: pass, 37 file.
- `.\.venv\Scripts\python.exe -u ../var/t05_verify_migrations.py` tại backend: pass; artifact local gọi đúng ba CLI upgrade/downgrade/upgrade trên DB mới `hr_ats_test_t05_cli_<uuid>` từ template0, kiểm head/schema sau từng bước và dọn đúng DB vừa tạo. Các lượt helper đầu gặp kết nối chưa có timeout đã được dừng đúng process và dọn đúng DB tạm sau khi xác minh; lượt cuối đặt connect_timeout cho mọi kết nối và exit 0. Không chạy downgrade trên hr_ats/hr_ats_test. Artifact ở var/ được gitignore.
- `git diff --check`: sạch. Tự review theo secure-code-review: SQL có tham số, quyền resource truy vấn DB, không cascade xoá dữ liệu, không raw CV/storage/PII trong log/schema công khai mới, không có dữ liệu/secret thật hoặc dependency mới. Không còn finding đã xác nhận chưa xử lý trong phạm vi T05.

File chính: `backend/app/models/{enums,mixins,jobs,candidates,applications,activity}.py`, `backend/migrations/versions/0003_core_data_model.py`, `backend/app/schemas/core.py`, `backend/app/core/{permissions,logging,config}.py`, `backend/app/services/activity.py`, `backend/tests/api/{test_core_data,test_database}.py`, `backend/tests/unit/test_logging.py`, README, spec 02/07/08, open-questions và PROGRESS.

ASSUMED: các mặc định nhỏ #22–#26 đã ghi rõ, không có blocker. Không tự tính consent/retention, không triển khai pipeline/endpoint của task sau.

NOT TESTED: CI remote (chưa push), review độc lập, benchmark dữ liệu production và migration thay đổi dimension trên dữ liệu thật. Frontend/E2E không bị ảnh hưởng bởi T05 (không thay endpoint/UI), không chạy lại. Cảnh báo upstream Starlette/httpx giữ nguyên như T02/T04, không tắt. Chờ `Review T05`, CI xanh và merge; chưa chuyển trạng thái `done`.

## T04 · 2026-11-08 · review

VERIFIED: triển khai T04 theo `tasks/_implement.md` trên nhánh `task/T04-auth-users-permissions`. T02/T03 đã `done`, working tree sạch trước khi bắt đầu. Hoàn thành triển khai, giữ trạng thái `review` cho đến khi được duyệt và merge vào main.

- Model/migration `users`: UUID, enum role, email lowercase unique/CHECK, Argon2id, trạng thái hoạt động, thời gian đăng nhập, bộ đếm sai, khoá tạm và phiên bản thu hồi token. Chỉ bổ sung chi tiết kỹ thuật phục vụ auth, chưa tạo bảng nghiệp vụ T05.
- API login/me/refresh/logout/change-password, bootstrap CSRF và list/create/patch users. JWT HS256 access 30 phút/refresh 7 ngày, cookie HttpOnly/SameSite=Lax/Secure khi prod; CSRF double-submit có chữ ký và gắn với phiên. Thu hồi token đã sao chép khi logout/đổi quyền/khoá/đổi mật khẩu; refresh chống replay. Khoá 15 phút sau 5 lần sai, cập nhật có row lock. Phiên bản cấp JWT được chụp trước commit để tránh nhận nhầm phiên đồng thời.
- `authorize(user, action, resource)` kiểm ma trận vai trò, mặc định từ chối; interface owner/member cho T05. Admin quản lý user, không cho tự khoá/tự bỏ quyền; CLI tạo admin hỏi mật khẩu hai lần, không in thông tin đăng nhập. Quản lý user có advisory transaction lock trước row lock actor để tránh deadlock khi hai admin sửa nhau.
- UI `/login`, bảo vệ route, hiển thị tên/đăng xuất, admin quản lý user tại `/settings` (phân trang, tạo, đổi vai trò, khoá/mở khoá có xác nhận). Recruiter không thấy Cài đặt và bị chuyển về Tổng quan khi mở URL trực tiếp; lead không có màn Người dùng. Tất cả chuỗi mới ở `vi.ts`; lỗi không phản chiếu message server. API client gộp refresh trong cùng tab và thử lại một lần; xoá query cache khi đổi tài khoản/đăng xuất.
- Cập nhật contract/spec 02/03/05/07/08, câu hỏi #18–#20, hướng dẫn CLI và nghiệm thu bằng DB tạm trong README. Không thêm dependency, không đổi stack, không sửa skill thư viện.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| API đăng nhập đúng/sai, khoá sau 5 lần, refresh, logout, recruiter `/users` 403, thiếu CSRF 403 | VERIFIED — đạt | `uv run pytest`: **152 passed**, gồm auth/users/concurrency; thêm bảng quyền, CLI, JWT hết hạn/sai loại/sai chữ ký, CSRF giả/khác phiên và thu hồi token |
| Đăng nhập UI vào được các trang; recruiter không thấy Cài đặt | VERIFIED — đạt | `npx playwright test`: **2 passed**, Chromium 1280×800 với API/Postgres thật trên DB tạm; admin đi đủ các trang, tạo/đổi quyền/khoá/mở khoá; recruiter `/users` 403, URL Cài đặt chuyển về Tổng quan; access mất được refresh, logout chặn truy cập lại |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, giữ các dịch vụ dev sẵn có.
- `uv sync`: pass, lockfile/dependency không thay đổi.
- `uv run alembic upgrade head`: pass trên DB dev, head `0002_users`. Pytest còn kiểm chứng upgrade → downgrade → upgrade từ DB trống, giữ extension và model khớp schema.
- `uv run pytest`: **152 passed, 1 warning**; không skip. Test khoá đăng nhập 5 request đồng thời không mất bộ đếm; 2 refresh cùng token chỉ 1 thành công. Dữ liệu giả, chỉ mạng localhost, không gọi LLM/embedding hay API bên ngoài.
- `uv run ruff check .`, `uv run ruff format --check .`: pass (50 file). `uv run mypy app`: pass (29 file).
- `npm ci`: pass, 536 package, **0 vulnerabilities**; giữ cảnh báo deprecation upstream của ESLint/whatwg-encoding.
- `npm run lint`, `npm run typecheck`: pass. `npm test`: **47 passed**; có guard, ẩn quyền Cài đặt, refresh đồng thời, lỗi thu hồi phiên và kiểm chuỗi JSX/i18n.
- `npm run build` với `NEXT_TELEMETRY_DISABLED=1`: pass, gồm `/login` và `/settings` mới.
- `uv run python -m tests.auth_browser_server`, `npm run dev`, `npx playwright test`: **2 passed**; server fixture migrate/seed tài khoản giả trên DB `hr_ats_test_t04_<uuid>`, API localhost:8000, frontend localhost:3000. Đã xem ảnh `var/t04-users.png`: tiếng Việt rõ, bảng 5 cột, đúng trạng thái/quyền, không tràn ở 1280px. Artifact nằm ngoài git.
- Sau nghiệm thu đã dừng đúng hai server kiểm thử và xoá duy nhất DB tạm T04 đã xác minh; kiểm tra DB `hr_ats`/`hr_ats_test` vẫn còn. Dịch vụ Docker dev được giữ lại.
- `git diff --check`: sạch. Tự review theo checklist `secure-code-review`: kiểm quyền tại service, validation input, cookie/JWT/CSRF, replay, transaction đồng thời, không log body/token/email/mật khẩu, không có PII/secret thật trong thay đổi. Regression test cho CSRF không hợp lệ và phiên bản JWT khi có phiên mới xen giữa; không còn finding đã xác nhận chưa xử lý trong phạm vi T04. Không thêm dependency; backend dependency audit riêng chưa chạy (không có công cụ audit trong manifest).

ASSUMED: mặc định kỹ thuật #18–#20: một phiên hoạt động/tài khoản, refresh có thời hạn 7 ngày kể từ lần cấp gần nhất, password mới 12–128 ký tự, web/API cùng hostname, không tự khoá/bỏ quyền admin, chưa ghi audit nghiệp vụ trước T17. Không có blocker.

NOT TESTED: GitHub Actions remote (chưa push), review độc lập, production HTTPS/reverse proxy và các luồng nghiệp vụ sau T04. Cảnh báo upstream Starlette TestClient/httpx vẫn giữ nguyên như T02, không tắt cảnh báo. Membership truy vấn DB thuộc T05; seed toàn hệ thống/E2E nghiệp vụ thuộc T18. Chờ `Review T04`, CI xanh và merge; không tự merge/push task nhạy cảm.

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
