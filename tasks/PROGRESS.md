# Tiến độ

| ID | Trạng thái | Ngày | Ghi chú |
|---|---|---|---|
| T01 | done | 2026-11-08 | Ba tiêu chí nghiệm thu đạt. MinIO (profile `s3`, tuỳ chọn) hoãn lại vì image không tải được; dùng `STORAGE_BACKEND=local`. Xem câu hỏi #8. |
| T02 | done | 2026-11-08 | Review lần 2: APPROVE WITH NITS, 76 test pass trên Postgres/Redis thật (tasks/reviews/T02.md). Nhắc việc N1→T05, N2→T14, N3→T26. |
| T03 | done | 2026-11-08 | VERIFIED: khung frontend Next.js 15, sáu trang tiếng Việt, API client và bộ component; 39 test pass, lint/typecheck/build sạch, smoke Chromium 1280px đạt. Chờ review và merge. |
| T04 | done | 2026-11-08 | VERIFIED: auth cookie JWT/CSRF, Argon2id, khoá đăng nhập, CLI admin và quản lý người dùng; 152 test backend, 47 test frontend, 2 E2E pass. Chờ Review T04 và merge. |
| T05 | done | 2026-11-08 | VERIFIED: 10 bảng lõi, migration/rollback, full-text không dấu, HNSW cosine, schema đọc, quyền DB owner/member, activity và che PII. 225 test backend pass; Ruff/mypy sạch. Chờ Review T05 và merge. |
| T06 | done | 2026-11-08 | VERIFIED: bộ sinh offline theo seed, 60 CV giả/60 nhãn, 5 Job/300 nhãn phù hợp, 6 nghề/6 bố cục; 9,76 MB. Backend 248 test pass, Ruff/mypy sạch; 22 test dữ liệu pass trên Linux, byte khớp Windows. Chờ Review T06 và merge. |
| T07 | done | 2026-11-08 | VERIFIED: storage local/S3, upload theo lô/chống trùng, quyền đọc/download/audit, ba queue Celery và worker tạm. 298 test backend pass (50 test T07), Ruff/mypy sạch; chờ Review T07, CI và merge. |
| T08 | done | 2026-11-08 | VERIFIED: review APPROVE; Fix round 1 sửa mypy Linux ở nhánh CREATE_NO_WINDOW bằng sys.platform. CI commit 7308023 xanh cả backend/frontend (run 42472261837), 419 test backend pass/0 skip gồm OCR thật; Ruff/mypy/migration sạch. Chờ merge. |
| T09 | done | 2026-11-08 | VERIFIED: bốn adapter JSON, schema parse/score, bốn prompt v1 tiếng Việt và CLI smoke; 136 test T09 pass, backend 543 pass/12 skip OCR Windows, Linux offline 257 pass/0 skip gồm OCR thật; Ruff/mypy/migration sạch. Chờ Review T09, CI và merge. |
| T10 | done | 2026-11-08 | VERIFIED: parse ba phần song song, dedupe email/SĐT/cosine và worker nguyên tử/idempotent; 586 test backend pass/12 skip OCR Windows, Linux offline 134 pass/0 skip gồm OCR thật; Ruff/mypy/migration sạch. Chờ Review T10, CI và merge. |
| T11 | done | 2026-11-08 | VERIFIED: ẩn danh trên 50 CV giả, fake/local embedding, hook pipeline/Job và CLI reembed nguyên tử; 691 test backend pass/12 skip OCR Windows, Linux offline 212 + 4 pass/0 skip; Ruff/mypy/migration sạch. Chờ Review T11, CI và merge. |
| T12 | done | 2026-11-08 | VERIFIED: chấm tiêu chí/bằng chứng, điểm tất định, worker và ba API có quyền/CSRF; 774 test backend pass/12 skip OCR Windows, Linux offline 242 pass/0 skip. Bộ mẫu 250/250 cặp đã chấm, 50/60 CV khớp cả 5 Job (83,3%); Ruff/mypy/migration sạch. Chờ Review T12, CI và merge. |
| T13 | done | 2026-11-08 | VERIFIED: API đơn vị/Job/members, quyền DB, validation, embedding và UI tiếng Việt; 819 backend pass/12 skip OCR cũ, 59 Vitest và 2 E2E pass, smoke T13 API thật 1280px đạt; lint/typecheck/migration/build sạch. Chờ Review T13, CI và merge. |
| T14 | done | 2026-11-08 | VERIFIED: API xếp hạng/thống kê đúng quyền, upload nhiều file/polling 3 giây và UI chi tiết Job tiếng Việt. 841 backend pass/12 skip OCR cũ, 69 Vitest và 3 E2E pass; lint/typecheck/migration/build sạch. Chờ Review T14, CI và merge. |
| T15 | done | 2026-11-08 | VERIFIED: API hồ sơ/audit, phản hồi AI upsert theo user, ghi chú và sửa ứng viên; drawer PDF/DOCX, tiêu chí/cờ Việt và lịch sử. 866 backend pass/12 skip OCR cũ, 77 Vitest và 4 E2E pass; lint/typecheck/migration/build sạch. Chờ Review T15, CI và merge. |
| T16 | done | 2026-11-08 | VERIFIED: kho CV tìm không dấu/theo nghĩa và bộ lọc, top-50 gợi ý theo Job, chọn nhiều tạo/chấm hồ sơ, gộp nguyên tử có xác nhận/giữ lịch sử. 893 backend pass/12 skip OCR cũ, 85 Vitest và 5 E2E pass; lint/typecheck/migration/build sạch. Chờ Review T16, CI và merge. |
| T17 | done | 2026-11-09 | VERIFIED: Fix round 1 sửa F1–F3; giữ cách escape an toàn của F4 theo review. Test export/migration PostgreSQL 8 pass, frontend 86 pass; lint/typecheck sạch. Xem nhật ký fix và tasks/reviews/T17.md. |
| T18 | done | 2026-11-09 | VERIFIED: seed dev idempotent chạy pipeline thật/FakeLLM, README Demo nhanh, M1 smoke với Celery/Redis thật và 6 E2E pass. Backend 908 pass/12 skip OCR sẵn có, frontend 86 pass; lint/typecheck/build sạch. M1 hoàn thành về chức năng; chờ review, CI và merge. |
| T19 | done | 2026-11-09 | VERIFIED: service move/undo nguyên tử, API pipeline tám cột và nhãn config; đủ 64 cặp stage, biên 24 giờ và quyền undo. Backend 1023 pass/12 skip OCR sẵn có, nhóm pipeline/core_data/system 184 pass; Ruff/mypy/migration sạch. Chờ Review T19, CI và merge. |
| T20 | done | 2026-11-09 | VERIFIED: Kanban dnd-kit chuột/bàn phím, cập nhật lạc quan/rollback, lý do từ chối, toast undo, drawer và email slot. Frontend 101 test và 7 E2E pass; lint/typecheck/build sạch. Chờ Review T20, CI và merge; sandbox chặn ghi .git nên thay đổi còn trong working tree. |
| T21 | done | 2026-11-09 | VERIFIED: Fix round 1 sửa F1, kiểm feedback theo interview ID thay vì vị trí theo UUID. Test F1 10/10 pass; toàn bộ backend 1052 pass/12 skip OCR cũ; Ruff/mypy sạch. Xem tasks/reviews/T21.md và nhật ký; chờ review lại, CI và merge. |
| T22–T33 | todo | | |

## Nhật ký
<!-- Agent thêm mục mới ở đầu: ## Txx · YYYY-MM-DD · done|blocked, rồi tóm tắt -->

## T21 · 2026-11-09 · fix round 1 · review

VERIFIED: làm theo `tasks/_fix.md` trên nhánh
`task/T21-interviews-offers-placements`; review có duy nhất F1 (BLOCKER).
Tái hiện assertion feedback lỗi do hai interview trùng scheduled_at nhưng ID
ngẫu nhiên quyết định thứ tự. Sửa `backend/tests/api/test_recruitment.py` để tìm
interview vừa PATCH theo ID trước khi kiểm feedback; giữ cả hai lịch trùng giờ
và toàn bộ assertion stage/history/ICS/quyền riêng tư/không gửi thư.

- VERIFIED: test nghiệm thu chạy riêng trước sửa có 2 pass rồi 1 fail tại
  assertion cũ; sau sửa chạy 10 lần độc lập liên tiếp đều pass.
- VERIFIED: `uv run ruff check .`, `uv run ruff format --check .` (143 file)
  và `uv run mypy app` (85 file) đều pass.
- VERIFIED: `uv run pytest` **1052 passed, 12 skipped, 1 warning / 1064 collected**
  trong 251,28 giây; gồm 29 recruitment, 115 pipeline và 7 migration test.
  Chỉ 12 test OCR T08 skip vì thiếu Tesseract theo ngoại lệ cũ; cảnh báo
  Starlette/httpx có sẵn. Không thêm skip, xoá test hoặc nới tiêu chí.
- VERIFIED: cache uv chuyển vào `var/uv-cache`, bật `UV_OFFLINE=1`. Lượt full
  đầu dừng vì sandbox chặn khoá thư mục tạm pytest; chẩn đoán xác nhận lỗi
  setup này. Chạy lại lệnh chuẩn với quyền được duyệt đã pass toàn bộ.
- NOT TESTED: frontend/E2E không chạy lại vì chỉ sửa assertion backend và hồ sơ task.
- VERIFIED: không đổi runtime, API, schema hoặc frontend; trạng thái giữ review
  đến khi được duyệt và merge. Chi tiết finding ở `tasks/reviews/T21.md`.
- VERIFIED: `git diff --check` pass. `git add` trước commit bị chặn
  `.git/index.lock` (Permission denied); theo ngoại lệ `_fix.md`, giữ thay đổi
  trong working tree trên nhánh T21, runner cần commit `T21: fix review findings`.

## T21 · 2026-11-09 · review

VERIFIED: đọc workflow `_implement.md`, task/spec 02/03/05 và quy định kiểm thử;
T19 đã done, working tree sạch khi bắt đầu. Nhánh có sẵn
`task/T21-interviews-offers-placements`; thử switch báo .git/index.lock
Permission denied. Theo ngoại lệ workflow, tiếp tục trên đúng nhánh hiện tại,
không tạo worktree hoặc sửa metadata Git. Giữ review đến khi được duyệt/merge.

- Thêm Interview/Offer/Placement và migration 0005: FK, soft delete, defaults,
  CHECK round/duration/status/tiền/ngày bảo hành/sent_at, UNIQUE placement theo
  Application kể cả đã ẩn và index cho drawer/khoảng lịch. Không sửa migration cũ.
- Service khoá Application và đọc lại record; thao tác nghiệp vụ/stage/event/
  activity cùng savepoint và commit. pipeline.move có commit=False cho caller
  ghép transaction, mặc định API T19 giữ nguyên. submitted→interview khi đặt
  lịch, interview→offer khi ghi sent, offer→hired khi nhận việc; cùng bước đích
  chỉ bổ sung record. Bước khác 409, không nhảy bước. Kết quả phỏng vấn và
  accepted/declined không tự loại/đổi stage; không AI hoặc gửi email.
- API tạo/sửa đủ ba thực thể, GET lịch [from,to) theo ngày Việt Nam/timestamp có
  offset, mine theo Application.owner_id cùng scope Job, pagination. Mở rộng
  profile có interviews/offers/placement, chỉ bản còn hiệu lực. Quyền Job từ DB,
  CSRF/Origin, input whitelist và no-store; Application owner không vượt Job.
- ICS bằng icalendar 6.3.2 (dependency duy nhất thêm, khóa uv.lock): VTIMEZONE,
  TZID Asia/Ho_Chi_Minh, UID ổn định từ UUID, DTSTAMP UTC, DTSTART/END và escape/
  fold UTF-8. Chỉ vòng/thời điểm/thời lượng/địa điểm, không CV/liên hệ ứng viên,
  feedback hay attendee. Không mở endpoint gửi thư hoặc tự gửi offer.
- Drawer form đặt lịch, kết quả/nhận xét, tải ICS, draft/sent/accepted/declined,
  nhận việc/phí/bảo hành/tình trạng. Chuỗi mới ở vi.ts; lỗi giữ input, khoá ghi
  khi chờ, refresh các query liên quan, toast undo và nút trong focus trap.
  Undo chỉ stage, giữ record để sửa; đóng drawer dọn toast và response muộn
  không tạo lại cache/toast. Render text escape, không truy cập URL do HR nhập.
- Seed mới thêm 5 interview/10 offer/5 placement giả cùng initial history và
  stage hired; seed lặp giữ ID/count/AI/stage HR sửa. Không sửa ngược hồ sơ có
  lịch sử từ trước hoặc sinh consent. Cập nhật spec 02/03/05/08 và câu hỏi #74–77.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Tạo interview chuyển stage đúng và ghi stage_events | VERIFIED — đạt | test_interviews_stage_history_results_and_ics_round_trip, test_no_stage_skipping_or_history_on_invalid_create, test_pipeline_and_record_roll_back_together; E2E drawer tạo/undo trên API thật |
| File .ics hợp lệ và parse lại được | VERIFIED — đạt | Calendar.from_ical kiểm TZID, giờ Việt Nam/UTC, 75 phút, UID, folding/ký tự đặc biệt và không injection; E2E tải đúng tên tệp |
| Placement duy nhất cho mỗi Application | VERIFIED — đạt | test_offer_draft_sent_accepted_and_placement_are_atomic kiểm API trùng/constraint SQL/undo giữ record; test_simultaneous_placements_have_one_winner với hai session PostgreSQL độc lập; E2E POST trùng 409 |

### Lệnh và kết quả

- `docker compose up -d db redis mailpit`: DB/Redis Running; Mailpit thất bại
  bind SMTP 1025 do Windows giữ cổng (vấn đề có sẵn). NOT TESTED: Mailpit runtime,
  không thuộc tiêu chí T21; mọi test dùng email_outbox bộ nhớ và không gửi thư.
- `uv add 'icalendar>=6,<7>'`: pass sau khi cấp quyền cache/mạng. Lần thử
  `--offline=false` bị uv từ chối cú pháp, không sửa dependency. `uv sync`: pass.
- `uv run alembic upgrade head`: pass DB local từ 0004→0005. Test DB tạm migrate
  trống→head→base→head và compare_metadata: **7 passed**; không xoá dữ liệu dev.
  `uv run alembic upgrade head --sql`: pass. Rollout/rollback có ghi trong spec 02.
- `uv run pytest tests/api/test_recruitment.py tests/api/test_pipeline.py -q`:
  **144 passed**, gồm 29 T21 và 115 pipeline. `uv run pytest`:
  **1052 passed, 12 skipped / 1064 collected**, một cảnh báo Starlette/httpx cũ.
  Chỉ 12 OCR T08 skip vì Windows thiếu Tesseract; không thay điều kiện skip,
  xoá test hoặc nới tiêu chí. Seed CLI thật trên DB tạm cũng pass trong bộ này.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, **143 files**.
  `uv run mypy app`: pass, **85 source files**.
- `npm ci`: pass, **539 package**, audit **0 vulnerabilities**. Cảnh báo
  deprecation whatwg-encoding/eslint có sẵn, không đổi thư viện frontend.
- Lượt test T21 đầu: 5 assertion pass nhưng Sonner có unhandled pointer capture
  thiếu trong jsdom; thêm hỗ trợ API trình duyệt như test board hiện có. Sửa
  locator Testing Library không hỗ trợ exact trước khi chạy typecheck cuối.
- `npm test`: **106 passed / 13 files**, gồm 5 test T21. `npm run lint`,
  `npm run typecheck`, `npm run build`: **pass** sau format Prettier. Không gọi
  mạng ngoài từ tests; giữ Sonner thật và chỉ mock API boundary/pointer capture.
- `uv run python -m tests.ranking_browser_server` + `npm run start` từ production
  build: pass trên DB/storage tạm, FakeLLM/FakeEmbedder/eager worker.
  `npx playwright test recruitment.spec.ts`: **1 passed**; lệnh chuẩn
  `npx playwright test`: **8 passed** trong 28,3s, gồm mọi bài cũ. Tài khoản T21
  riêng, DOCX giả cv_0044 chỉ thêm ZIP comment transport, không sửa mẫu gốc.
- Đã xem ảnh var/t21-recruitment.png ở 1280px: hai cột/drawer/form vừa chiều
  ngang; E2E kiểm không overflow/lỗi JavaScript, persistence sau reload và
  undo từ focus trap. Ảnh/trace/runtime không track. Đã dừng API/web, fixture
  tự dọn đúng DB/storage dùng một lần và stop file; giữ DB/Redis dev.
- Tự review theo secure-code-review: auth/scope/CSRF đầy đủ, query bind, ID header
  từ UUID, không log nội dung/names/feedback, không HTML thô hoặc fetch link HR,
  không gửi thư, rollback và concurrency có bằng chứng test. Schema/API/KPI
  ngoài T21 được giữ; không có dữ liệu thật hoặc thay đổi skill files.
- `git diff --check`: pass. Ghi Git bị sandbox chặn .git/index.lock; runner cần
  commit `T21: implement interviews offers and placements` từ working tree.

### Câu hỏi / việc còn lại

ASSUMED: #74–#77 về stage/undo, DTO/vòng đời, mine/khoảng lịch/ICS và seed.
NOT TESTED: benchmark production, SMTP/provider thật, CI hoặc review độc lập.
Không có tiêu chí T21 bị chặn; chờ Review T21, CI và merge, chưa tự chuyển done.

## T20 · 2026-11-09 · review

VERIFIED: T19 đã done, working tree sạch khi bắt đầu và nhánh có sẵn là
`task/T20-kanban-ui`. Triển khai đúng T20 theo `_implement.md`; giữ review cho
đến khi được duyệt và merge main.

- Tab Quy trình dùng `@dnd-kit/core` (đã chỉ định trong spec 01/T20). Bảy cột
  mặc định, withdrawn trong Xem thêm, cuộn ngang riêng ở 1280px. Thẻ hiện tên,
  mức/trạng thái AI, số ngày ở bước và tooltip thời điểm Việt Nam; nhấn tên mở
  drawer T15, đóng trả focus. Tay nắm dùng chuột hoặc Space/Enter và mũi tên;
  toàn bộ hướng dẫn/nhãn trình đọc màn hình và chuỗi mới nằm trong vi.ts.
- Move cập nhật thẻ/count/timestamp trước response; lỗi khôi phục snapshot và
  báo tiếng Việt. Khoá thao tác ghi/polling trong lúc chờ, cùng cột/Escape/thả
  ngoài cột không gọi API. Rejected bắt chọn một trong sáu lý do T19, huỷ không
  gửi; đang lưu không đóng/bấm lặp, lỗi giữ lý do. Không kéo tiếp từ stage kết
  thúc; API T19 vẫn là nơi kiểm quyền và quy tắc chuyển bước.
- Toast thành công có Hoàn tác POST /undo, cập nhật từ response và làm mới
  pipeline/xếp hạng/lịch sử. Giữ board sau khi mở tab lần đầu để undo vẫn hoạt
  động khi đổi tab; tab ẩn dừng polling. Mỗi hồ sơ chỉ giữ toast lần chuyển mới
  nhất. Dọn toast có tên khi rời trang; response về sau unmount không khôi phục
  dữ liệu cache hay hiển thị tên sau khi đăng xuất. Có test hồi quy.
- Email slot chỉ mở dialog khi suggested_email khác null, giữ payload opaque
  vì T19 chưa có contract nháp. Không render payload hoặc gửi email; form sửa
  và xác nhận gửi thuộc T23. Cập nhật spec 05/08 và câu hỏi #72–#73, không đổi
  schema, endpoint hoặc backend runtime.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Kéo thẻ gọi API đúng | VERIFIED — đạt | pipeline-board.test.tsx dùng DndContext/KeyboardSensor thật, kiểm POST/body một lần và thẻ đổi cột khi response còn chờ; E2E chuột trên API thật |
| Lỗi API → thẻ về cột cũ và thông báo | VERIFIED — đạt | Test request chờ rồi reject kiểm tên/count/timestamp cũ, không lộ exception; E2E new→submitted nhận 409 và hiển thị lỗi Việt |
| Hoàn tác hoạt động | VERIFIED — đạt | Component test POST undo và cập nhật cột/lịch sử, lỗi 24h không đổi thẻ; E2E đổi tab rồi undo, từ chối có lý do rồi undo/reload vẫn đúng |

### Lệnh và kết quả

- `npm install @dnd-kit/core`: lần đầu ENOTCACHED do cache-only sandbox; chạy
  với quyền mạng và `--offline=false` thành công. Dependency thêm chỉ core và
  hai dependency MIT của dnd-kit. `npm ci`: pass, 539 package; audit **0 lỗ hổng**.
  Giữ warning deprecation có sẵn của whatwg-encoding/eslint, không đổi stack.
- `npm test`: **101 passed / 12 files**, gồm 11 test board mới và 4 test dịch
  mã lỗi pipeline. Vitest ban đầu bị sandbox Windows chặn spawn EPERM; chạy
  với quyền tạo tiến trình thì pass. Giữ DndContext/sensor/Sonner thật; mock
  API boundary, geometry và pointer capture còn thiếu của jsdom.
- Lượt test đầu phát hiện toast undone dùng lại ID toast vừa bị Sonner đóng;
  sửa code dùng ID mới, không nới assertion. Bài regression undo pass cùng bộ
  cũ. `npm run lint`, `npm run typecheck`, `npm run build`: **pass**.
- `docker compose up -d db redis`: pass sau khi cấp quyền Docker pipe.
  `uv run python -m tests.ranking_browser_server`: pass trên DB/storage tạm,
  migrate từ trống qua revision 0004, FakeLLM/FakeEmbedder/eager worker.
- `npx playwright test pipeline.spec.ts`: **1 passed**, kiểm chuột/bàn phím,
  reject/undo/rollback, menu/drawer/focus và không tràn trang. Lượt chuẩn bị đầu
  sửa locator Playwright, rồi thay CV scan 0042 bằng DOCX giả 0043 vì Windows
  thiếu OCR; không đổi điều kiện skip, dữ liệu gốc hoặc tiêu chí của test cũ.
- `npx playwright test` với dev server: **4 passed / 3 failed** ở timeout điều
  hướng các bài cũ. Log Next.js xác nhận compile lạnh route mất 6–8 giây, quá
  assertion 5 giây. Dừng dev, `npm ci` và `npm run build`, chạy `npm run start`
  rồi tạo lại fixture sạch: lệnh chuẩn `npx playwright test` **7 passed** với
  6 worker trong 25,2 giây. Không tăng timeout, sửa hoặc bỏ bài test cũ.
- Đã xem ảnh var/t20-pipeline.png và var/t20-rejection.png ở 1280px. Tự review
  theo secure-code-review: giữ cookie/CSRF client, không log dữ liệu, render text
  escape, không gửi email, dọn dữ liệu khi rời trang; audit dependency không có
  finding. Ảnh/trace/runtime không track trong repo.
- `git diff --check`: pass. `git add` bị từ chối tạo .git/index.lock do sandbox
  chỉ đọc .git; theo ngoại lệ `_implement.md`, giữ nguyên nhánh và mọi thay đổi
  trong working tree để runner commit. Chưa push/merge, chưa có kết quả CI/review
  độc lập. Backend test/lint/mypy không chạy lại vì không sửa backend/schema;
  migration và API thật được kiểm qua fixture E2E.

### Câu hỏi / việc còn lại

- ASSUMED #72: ngày tròn mỗi 24 giờ, cột withdrawn bật trong menu và thao tác
  bàn phím; #73: slot giữ bản nháp opaque đến contract T23.
- Chờ Review T20, CI và merge; runner cần commit `T20: implement pipeline kanban`.
  Không có tiêu chí nghiệm thu T20 bị chặn.

## T19 · 2026-11-09 · review

VERIFIED: T18 đã done, working tree sạch khi bắt đầu, nhánh đã có sẵn là
`task/T19-pipeline-service-api`; triển khai đúng một task theo `_implement.md`.
Giữ T19 ở review đến khi được duyệt và merge main.

- `services/pipeline.py` kiểm ma trận bước kế/lùi và kết thúc, khoá/đọc lại
  Application trước khi kiểm quyền và ghi. Move/undo cùng transaction với
  StageEvent và activity stage_changed, giữ owner/AI, rollback toàn bộ khi lỗi.
  Undo chỉ lần đổi gần nhất trong 24 giờ, đúng actor hoặc admin/lead, ghi event
  mới và metadata undo_of; không xoá lịch sử hoặc cho undo event hoàn tác.
- API move trả ApplicationRead cùng suggested_email=null; undo trả
  ApplicationRead. Lý do từ chối bắt buộc trong sáu chuỗi chuẩn. Pipeline trả
  đủ tám cột/card tối thiểu, cùng quyền Job/eligibility T14; config thêm nhãn
  theo spec 02 và HIRING_UNIT_LABEL. Không gọi AI, queue hoặc gửi email.
- Lượt hồi quy đầu phát hiện log_activity nhận nhầm một phần UUID ngẫu nhiên
  thành SĐT, cũng ảnh hưởng stage_event_id/undo_of mới. Đã tái hiện bằng ba
  test thất bại trước sửa. Sửa hẹp helper nhận diện UUID v4 canonical chỉ ở
  *_id/undo_of, giữ kiểm PII/khoá nhạy cảm cho dữ liệu khác; test âm và toàn bộ
  fixture/assertion core_data cũ được giữ. Không đổi bộ lọc log chung.
- Cập nhật contract spec 02/03, kiểm thử spec 08 và câu hỏi #68–#71; không thêm
  migration, dependency, UI hoặc nghiệp vụ interview/offer/placement của T21.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Mọi cặp chuyển stage hợp lệ/không hợp lệ | VERIFIED — đạt | test_all_64_stage_pairs_and_undo_valid_changes: 64 cặp, ma trận kỳ vọng độc lập từ spec, undo mọi move hợp lệ và kiểm event/activity gốc còn nguyên |
| Undo quá 24 giờ bị từ chối | VERIFIED — đạt | test_undo_24_hour_boundary: 24h ±1 microsecond, đúng 24h, mốc tương lai; đúng biên được phép, quá hạn bị UNDO_EXPIRED |
| Recruiter khác người đổi bị từ chối undo | VERIFIED — đạt | test_other_recruiter_cannot_undo_but_lead_and_admin_can: recruiter member cùng Job nhận UNDO_FORBIDDEN, lead/admin có quyền hoàn tác |

### Lệnh và kết quả

- `docker compose up -d db redis mailpit`: DB/Redis local running; Mailpit
  không bind được SMTP 1025 do Windows giữ cổng như T18. NOT TESTED: Mailpit
  runtime; T19 kiểm không gửi email với outbox trong bộ nhớ.
- `uv sync`: pass; `uv run alembic upgrade head`: pass, schema không đổi.
- Trước sửa UUID: nhóm pipeline/system **116 passed**; core_data riêng
  **60 passed**. Lượt `uv run pytest` đầu **1014 passed, 12 skipped, 1 error**
  ở fixture core_data do UUID, không phải assertion được nới để bỏ qua.
- `uv run pytest tests/api/test_pipeline.py -k uuid_metadata -q`: **3 failed**
  trước sửa, tái hiện đúng lỗi #71. Sau sửa,
  `uv run pytest tests/api/test_pipeline.py tests/api/test_core_data.py tests/api/test_system.py -q`:
  **184 passed**, một cảnh báo Starlette/httpx có sẵn.
- `uv run pytest` sau sửa: **1023 passed, 12 skipped** (1035 collected),
  một cảnh báo Starlette/httpx có sẵn. Chỉ 12 OCR T08 skip do thiếu Tesseract
  trên Windows; giữ nguyên điều kiện skip. Toàn bộ test cũ và mới pass.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 137 file.
  `uv run mypy app`: pass, 81 source file. `git diff --check`: pass.
- Tự review theo secure-code-review: service kiểm quyền từ DB, auth/CSRF,
  input whitelist, query bind, DTO tối thiểu, note chỉ ở event DB nghiệp vụ,
  không log CV/ghi chú; rollback và hai session PostgreSQL độc lập kiểm move/
  undo đồng thời chỉ ghi một lượt. Không thay điều kiện skip hoặc xoá test cũ.
- `git add backend/app/services/pipeline.py` không tạo được `.git/index.lock`
  (Permission denied). Theo fallback `_implement.md`, giữ toàn bộ thay đổi
  trong working tree trên nhánh T19 để runner commit
  `T19: implement pipeline service and APIs`.

ASSUMED: mặc định về single undo, response shape, note/lý do và thứ tự card ở
#68–#70. NOT TESTED: tải/hiệu năng production, giao diện kanban T20, provider
thật. Review T19, CI và merge còn chờ; không tự chuyển trạng thái done.
Fixture test đã tự dọn DB tạm; không khởi động API/worker/web hoặc xoá dữ liệu
dev trong lượt này. Frontend/E2E không chạy vì T19 chỉ thay backend và spec.

## T18 · 2026-11-09 · review

**M1 hoàn thành** — VERIFIED về chức năng: tạo Job, tải CV, xếp hạng có lý do,
phản hồi AI, tìm Kho CV và xuất Excel đã có kiểm chứng. T18 giữ `review` cho
đến khi review/CI/merge; chưa tự chuyển task sang `done`.

VERIFIED: bắt đầu trên nhánh `task/T18-seed-and-first-e2e`, working tree sạch,
T16/T17 đều `done`; triển khai theo `tasks/_implement.md`.

- `app/scripts/seed.py` tạo 4 tài khoản giả, 3 đơn vị tuyển, 5 Job từ jobs.json,
  40 CV kỹ thuật số/hồ sơ qua upload → extract → parse → ẩn danh → embedding →
  chấm điểm thật với fake provider. CLI dùng task eager và kết nối worker độc
  lập, kiểm done trước khi thành công; upload web tiếp tục dùng Celery/Redis.
- Seed từ chối prod/provider thật/DB ngoài localhost/storage từ xa, không reset
  password/quyền hoặc suy diễn consent. Lặp lại giữ ID/score/lịch sử/stage HR
  đã sửa; phục hồi lượt dở dang. Lịch sử stage được tạo rõ là dữ liệu giả.
  Không thêm migration; các bảng module tương lai theo câu hỏi #66.
- FakeLLM bổ sung đọc một dòng danh sách kỹ năng sau tiêu đề riêng dòng; có
  test chống nuốt mục sau. Không sửa nhãn/prompt/công thức score/provider thật
  hoặc suy đoán tên từ header. Câu hỏi #67 ghi lỗi tái hiện và lựa chọn này.
- `m1-smoke.spec.ts` đăng nhập recruiter, tạo Job kế toán bằng form từ nhãn
  jobs.json, thả 5 CV, đối chiếu cả thứ tự mức AI (dòng đầu high), gửi/mở lại
  phản hồi khác mức, tìm bookkeeping và kiểm ứng viên thuộc batch vừa tải.
  ZIP/PDF comment chỉ thay hash payload để chạy lại trên dev mà giữ file gốc.
- README **Demo nhanh** ghi đầy đủ cài đặt/migrate/seed/API/worker/web/trình
  duyệt, tài khoản giả, E2E và fallback cổng Mailpit. Fixture trình duyệt T14
  tái sử dụng catalog T18; selector link T14 xác định đúng ID Job khi có tên
  trùng, giữ mọi assertion cũ. Đã xem screenshot Kho CV ở 1280px, không tràn
  ngang hoặc lỗi JavaScript; screenshot/artifact chỉ ở thư mục bị gitignore.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Từ repo sạch làm theo Demo nhanh chạy được và E2E pass | VERIFIED — đạt | CLI subprocess trên DB trống đã migrate, seed hai lần không tăng số row/file hoặc ghi đè stage; `uv run python -m app.scripts.seed` trên DB dev thành công; smoke với API/worker Redis thật **1 passed**; `npx playwright test` trên DB/storage tạm mới **6 passed** |
| Đánh dấu mốc M1 hoàn thành | VERIFIED — đạt | Mốc ở đầu nhật ký này và dòng T18; trạng thái task vẫn `review` chờ duyệt/CI/merge |

### Lệnh và kết quả

- `docker compose up -d db redis mailpit`: DB/Redis chạy; Mailpit lỗi bind
  SMTP 1025 bị Windows giữ. Fallback README `docker compose up -d db redis`:
  pass. NOT TESTED: runtime Mailpit lượt này; M1 không gửi email.
- `uv sync`: pass; `uv run alembic upgrade head`: pass. Test DB riêng chạy
  lịch sử Alembic từ template0; không thay schema, không reset DB dev/test.
- `uv run python -m app.scripts.seed`: pass, đủ 4/3/5/40; test CLI hai lần
  và test seed tiếp tục sau lỗi pipeline cũng pass.
- `uv run pytest`: **908 passed, 12 skipped**, 1 cảnh báo Starlette/httpx
  có sẵn; 12 skip OCR theo T08 do không có Tesseract, không đổi điều kiện.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 134 file.
  `uv run mypy app`: pass, 79 source file.
- `npm ci`: pass, 0 vulnerability; `npm test`: **86 passed**.
  `npm run lint`, `npm run typecheck`, `npm run build`: pass.
- `npx playwright install chromium`: pass; smoke M1 trên demo dùng Uvicorn
  `--reload`, worker Windows `-P solo`, Redis thật và Next dev: **1 passed**.
  `npx playwright test` với fixture DB riêng và production web: **6 passed**.
  Lần đầu bộ E2E phát hiện selector T14 trùng tên Job; đã sửa định danh link,
  chạy lại cả suite trên fixture mới, giữ đủ 6 bài và mọi tiêu chí.
- `git diff --check`: pass. Đã tự review diff về phạm vi, trường hợp lỗi và
  PII; chỉ dữ liệu giả, không có secret thật, không có kết nối provider thật.
- `git add` thất bại vì không tạo được `.git/index.lock` (Permission denied),
  nên chưa commit. Theo fallback trong `tasks/_implement.md`, giữ nguyên toàn
  bộ thay đổi ở working tree trên nhánh task để runner commit. Đã dừng các
  API/worker/web do lượt kiểm thử khởi động; fixture dọn xong DB/storage tạm,
  truy vấn không còn DB `hr_ats_test_t%`; giữ DB dev/test và dữ liệu demo.

ASSUMED / việc còn lại: dữ liệu interview/offer/placement/task/email mẫu theo
#66 được bổ sung khi task sở hữu bảng triển khai. Review T18, CI và merge còn
chờ quy trình ngoài lượt implement này; chưa kiểm provider/model AI thật.

## T17 · 2026-11-09 · review · Fix round 1

VERIFIED: xử lý review theo `tasks/_fix.md`, giữ nhánh
`task/T17-excel-export-audit`. T17 giữ trạng thái `review` cho đến khi được
duyệt và merge vào main.

- F1: thêm fixture `records` cục bộ tạo đơn vị, Job do account sở hữu và ứng
  viên giả còn hạn. Đã tái hiện lỗi thiếu fixture trước khi sửa.
- F2: đã tái hiện sai kỳ vọng SĐT sau khi sửa fixture; kỳ vọng mới giữ dấu
  apostrophe do cơ chế chống công thức. Đọc workbook không dùng cached formula
  và kiểm ô tên/SĐT có kiểu chuỗi; không đổi bảo vệ trong service export.
- F3: Prettier định dạng lại đúng hai file `job-detail.tsx` và
  `job-detail.test.tsx`; không thay hành vi giao diện.
- F4: không sửa ghi chú UX tuỳ chọn; giữ dấu apostrophe để escape chuỗi bắt
  đầu bằng ký tự công thức, đúng trade-off mà review chấp nhận.
- Phát hiện thêm test migration cũ còn kỳ vọng revision 0003. Sửa kỳ vọng
  thành `0004_audit_details` của T17, giữ đủ upgrade/rollback/upgrade và đối
  chiếu schema. `uv run pytest tests/api/test_database.py tests/api/test_export.py`:
  **8 passed**, 1 cảnh báo Starlette/httpx có sẵn.
- `npm test -- --maxWorkers=1`: **86 passed**. Lần `npm test` chạy song song
  với các kiểm tra khác có 85 pass/1 timeout 5 giây ở test kho CV T16; chạy
  lại toàn bộ bằng một worker pass, không đổi test hoặc timeout.
- `uv run pytest`: **893 passed, 12 skipped, 1 failed** ở lượt khởi chạy trước
  khi sửa kỳ vọng revision; lỗi duy nhất là hàm migration đã nạp vẫn so với
  0003. Sau khi lượt này kết thúc, `uv run pytest --lf`: **1 passed** trên mã
  hiện tại; bộ database/export ở trên cũng **8 passed**. Không chạy lại toàn
  bộ từ đầu sau sửa một kỳ vọng test. 12 skip do thiếu Tesseract theo ngoại lệ
  T08; giữ nguyên điều kiện skip/timeout. Cảnh báo Starlette/httpx có sẵn.
- `uv run ruff check .`, `uv run ruff format --check .` (131 file),
  `uv run mypy app` (78 file), `uv run alembic upgrade head`, `npm run lint`,
  `npm run typecheck`, `npm run build` (tắt telemetry): **PASS**.
- `git diff --check`: **PASS**; tự rà soát diff không có thay đổi ngoài T17.
- Chưa tạo commit `T17: fix review findings`: `git add` không tạo được
  `.git/index.lock` do `Permission denied`. Theo fallback của `tasks/_fix.md`,
  giữ toàn bộ thay đổi trên nhánh T17 để runner commit. Chờ review lại/CI/merge.

File chính: `backend/tests/api/test_export.py`, `test_database.py`, hai file
frontend nêu trên, `tasks/reviews/T17.md`, `tasks/PROGRESS.md`. Bằng chứng và
quyết định từng finding được ghi trong `tasks/reviews/T17.md` mục Fix round 1.

## T16 · 2026-11-08 · review

VERIFIED: làm đúng một task theo `tasks/_implement.md` trên nhánh
`task/T16-cv-bank-search-suggest-merge`; T15 đã done, working tree sạch khi bắt
đầu. Trạng thái review đến khi được duyệt và merge vào main.

- API kho CV dùng DTO tóm tắt riêng, không xuất email/phone/consent/raw CV/
  parsed_json/vector hoặc Job membership. Full-text unaccent theo trigger T05,
  filter kỹ năng đủ tất cả/năm KN/địa điểm/nguồn, phân trang và thứ tự ổn định.
  Semantic gọi adapter T11 bằng câu tìm đã che liên hệ/metadata có nhãn, lỗi
  provider an toàn, không fallback. Bỏ ứng viên đã xoá/gộp/hết hạn ở mọi mode.
- Gợi ý top-50 cosine theo vector Job, kiểm quyền Job từ DB trước kể cả rỗng;
  loại Application đang hoạt động, vẫn cho bản đã soft delete; Job thiếu vector
  trả rỗng. Nhãn nghi trùng từ hint T10 đọc theo lô, đối xứng, chỉ hai bên hợp
  lệ; không đọc raw CV hoặc tự kết luận gộp.
- Merge chỉ admin/lead sau xác nhận, khoá identity T10 và Candidate/Application
  theo ID. Chuyển toàn bộ file/hồ sơ/activity về đích, soft delete nguồn; khi
  cùng Job giữ hồ sơ đích và lưu trữ bản nguồn trước đổi candidate_id để giữ
  unique partial. Giữ ID/StageEvent/AiFeedback gốc, consent/retention/vector của
  đích và stage/owner/AI của hồ sơ được giữ. Activity note chỉ action/source_id/
  target_id cùng transaction, test lỗi chứng minh rollback. Không hard delete,
  tự gia hạn, đổi stage, tự chấm lại hoặc gửi email. T12 khoá/đọc lại Candidate
  trước insert; test hai kết nối độc lập không cho tạo hồ sơ từ nguồn vừa gộp.
- `/candidates` có tìm kiếm/bộ lọc, thẻ ba cột, chọn nhiều và hộp chọn Job có
  quyền/phân trang. Hộp gộp so sánh hai bên, chọn bản giữ, cảnh báo hậu quả,
  focus Huỷ và xác nhận rõ ràng; recruiter nhận hướng dẫn nhờ trưởng nhóm.
  Trong Job có Thêm từ kho CV, gợi ý/chọn nhiều, mỗi người gọi POST T12 riêng;
  lỗi một người không chặn người khác, chỉ giữ người lỗi để retry. Hiển thị
  riêng already exists/đã thêm nhưng chấm lỗi; khoá đóng khi đang lưu.
  Tải/rỗng/lỗi/retry, nhãn select htmlFor/id, toàn bộ chuỗi mới trong vi.ts.
- Tự rà soát theo secure-code-review: quyền service/CSRF/Origin, SQL bind,
  DTO tối thiểu, React escape, lỗi an toàn, không log input/CV, khoá/rollback.
  Không thay schema, dependency, stack hoặc quy tắc chấm điểm. Spec 03/04/05/07/08
  cập nhật contract và mặc định ASSUMED #62–#64. Review độc lập/CI còn chờ.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Tìm "ke toan" ra CV có "Kế toán" | VERIFIED — đạt | `test_ke_toan_finds_accented_cv_and_returns_only_summary`; E2E `cv-bank.spec.ts` tìm không dấu qua API thật và thấy hai thẻ Kế toán |
| Gợi ý không trả người đã có trong Job | VERIFIED — đạt | `test_suggestions_exclude_existing_and_limit_to_top_50`, kiểm lại popup sau khi thêm ở E2E; test thêm cho Application đã lưu trữ, vector rỗng, quyền/thu hồi membership |
| Gộp xong không có Application trùng cùng Job | VERIFIED — đạt | `test_merge_moves_files_and_apps_without_duplicate_active_job_and_keeps_history` cho admin/lead: một active/Job, bản trùng soft delete; E2E gộp hai người đã vào hai Job rồi kiểm mỗi Job total=1; `test_t16_creation_waiting_on_merge_cannot_recreate_source_application` |

### Lệnh và kết quả

- `docker compose up -d db redis mailpit`: VERIFIED — ba service local running.
- Backend: `uv run pytest`: VERIFIED — **893 passed, 12 skipped** (905 collected),
  chỉ 12 OCR T08 thiếu Tesseract trên Windows, không thêm skip hoặc nới test.
  Bao gồm 26 test API T16 và một test cạnh tranh PostgreSQL mới. Fixture chặn
  mạng ngoài, fake provider và dữ liệu giả; schema/upgrade/rollback DB trống
  vẫn trong bộ test cũ. Lượt đầu sandbox lỗi quyền tempfile, chạy lại ngoài
  sandbox theo approval thành công, không thay fixture để bỏ kiểm tra.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app`,
  `uv run alembic upgrade head`: VERIFIED — sạch, 127 file format/76 source
  typecheck, head không cần revision mới.
- Frontend: `npm test`: VERIFIED — **85 passed / 11 files**;
  `npm run lint`, `npm run typecheck`, `npm run build`: VERIFIED — sạch.
- `uv run python -m tests.ranking_browser_server`, production frontend
  `npm run start`, `npx playwright test`: VERIFIED — **5 passed** trên API/DB/
  storage thật dùng một lần, gồm T16 và bốn E2E cũ. Bản build cuối chạy tuần tự
  với server, không cùng ghi `.next`. E2E đầu phát hiện nhãn select lẫn option,
  sửa liên kết label/id và chạy lại đạt, không thay tiêu chí để lách lỗi.
- VERIFIED: xem ảnh `var/t16-bank.png`, `var/t16-merge.png`,
  `var/t16-suggestions.png` ở viewport 1280×800; thẻ/hộp hai cột đọc được,
  không overflow ngang/lỗi JS. Artifact là dữ liệu giả trong thư mục gitignore.
- `git diff --check`: VERIFIED — sạch.

ASSUMED: chỉ admin/lead gộp, giữ bản đích và lưu trữ hồ sơ xung đột theo #62–#64.
NOT TESTED: chất lượng semantic bằng model local thật/hiệu năng kho production;
fake chỉ kiểm chức năng. Chưa có UI đọc Application đã lưu trữ sau gộp; ID và
lịch sử được giữ trong DB. Chờ Review T16, CI và merge; không tự đặt done/push.

## T15 · 2026-11-08 · review

VERIFIED: triển khai đúng một task theo `tasks/_implement.md` trên nhánh
`task/T15-candidate-drawer-ai-feedback`; T14 đã done và working tree sạch trước
khi bắt đầu. Giữ review đến khi được duyệt và merge vào main.

- Thêm GET chi tiết Application/Candidate, file DTO tối thiểu (text chỉ DOCX),
  phản hồi riêng của caller và activities đúng Application. Kiểm quyền Job từ DB,
  bỏ hồ sơ/ứng viên đã xoá, gộp hoặc hết hạn; kiểm quyền từng file. Ghi audit
  `action=view, entity=candidate` trước khi trả nội dung, IP kết nối được kiểm
  định và không tin X-Forwarded-For. Không xuất storage_key/parsed_json/vector.
- POST ai-feedback atomic upsert theo unique application/user; gửi lần hai giữ
  id và thay phản hồi trước. User lấy từ phiên; disagree cần mức sửa, comment
  tuỳ chọn; activity ai_feedback chỉ verdict/level, cùng savepoint/transaction
  với upsert. Test lỗi ghi activity chứng minh rollback cả phản hồi. Không đổi
  điểm AI/stage/owner hay gửi email.
- POST notes kiểm quyền rồi lưu Activity note có text HR nhập trong DB nghiệp
  vụ; không nới helper log_activity metadata và không log nội dung. PATCH ứng
  viên whitelist bảy trường tên/liên hệ/địa điểm/chức danh/năm KN/kỹ năng,
  chỉ sửa trường gửi lên; kiểm quyền Candidate qua Job hiện hành. Không sửa
  consent/retention/CV/vector hoặc tự gọi lại AI. Input thừa/sai bị từ chối,
  các mutation giữ CSRF/Origin, response thành công no-store.
- Drawer hai cột tối đa 1200px có chọn bản CV, viewer PDF/ảnh dùng byte qua
  endpoint download có quyền/audit và URL blob được thu hồi khi đóng/đổi file;
  DOCX là text thuần. Bên phải có thông tin sửa được/nhắc consent, nhãn/điểm
  tham khảo/lý do, bốn kết quả tiêu chí kèm trích dẫn, năm cờ dịch tiếng Việt và
  fallback cho mã không biết. insufficient hiện đúng câu trong task. Có Đồng ý/
  Không đồng ý, chọn mức và bình luận; lịch sử mới trước, ô ghi chú; tải/lỗi/
  thử lại, giữ nội dung khi lỗi lưu. Escape/Đóng trả focus; tiêu đề/bảng cập nhật
  tên sau sửa. Chuỗi mới trong vi.ts, không render HTML/payload/mã kỹ thuật.
- Cập nhật contract spec 02/03/05/08 và mặc định #59–#61. Không đổi schema,
  công thức AI, dependency, stack hoặc scope task sau.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Phản hồi lần hai của cùng user ghi đè lần một | VERIFIED — đạt | `test_feedback_second_submission_overwrites_same_user_without_changing_ai_or_stage`: giữ id, một row, thay verdict/level/comment; user khác độc lập, hai activity; E2E đồng ý → không đồng ý và mở lại dữ liệu đã lưu |
| Recruiter không có quyền Job → 403 | VERIFIED — đạt | `test_every_endpoint_checks_current_job_scope[outsider/revoked]` cho cả bốn endpoint; owner Application riêng không cấp quyền, không có activity/audit khi bị từ chối |
| Mở chi tiết ghi audit candidate.view | VERIFIED — đạt | `test_detail_records_candidate_view_and_exposes_only_authorized_docx_text`: action=view/entity=candidate, đúng actor/ứng viên, không tin header IP; response no-store |
| UI không hiện bốn thuật ngữ kỹ thuật trong task | VERIFIED — đạt | `vi.test.ts` kiểm toàn dictionary, `candidate-profile.test.tsx` kiểm nội dung/cảnh báo/fallback; E2E đọc nội dung drawer, i18n-usage kiểm chuỗi JSX/nhãn lấy từ vi.ts |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, giữ nguyên volume dev.
- Backend: `uv sync`, `uv run alembic upgrade head`: pass, head giữ
  `0003_core_data_model`. `uv run pytest`: **866 passed, 12 skipped, 1 warning**,
  tổng 878 test, 164,18s. Bộ T15 riêng **25 pass**. Skip chỉ OCR T08 do thiếu
  Tesseract Windows; không thay test cũ/điều kiện skip. Warning upstream
  Starlette/httpx có sẵn. PostgreSQL/Redis local, fake provider, không mạng ngoài.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 123 file.
  `uv run mypy app`: pass, 73 source file. `git diff --check`: pass.
  Dùng UV_CACHE_DIR trong var; chạy test với quyền local vì cache/tmp Windows.
- Frontend: `npm ci`: pass, 536 package, audit **0 vulnerabilities**; giữ warning
  deprecation upstream. `npm test`: **77 pass**, 10 file, không skip/mạng ngoài.
  `npm run lint`, `npm run typecheck`: pass. `npm run build` với
  NEXT_TELEMETRY_DISABLED=1: pass, `/jobs/[id]` 13,2 kB / 162 kB first load JS.
- `uv run python -m tests.ranking_browser_server` + `npm run dev`, sau đó
  `npx playwright test`: **4 pass**, 14,6s, gồm ba bài cũ. Bài T15 dùng account
  riêng, DOCX/PDF kỹ thuật số giả T06; thêm/sửa/phản hồi/ghi chú và mở lại với
  API thật, FakeLLM/eager. Đã xem `var/t15-profile-docx.png` và
  `var/t15-profile-pdf.png`: nội dung CV hiển thị, không tràn ở 1280px/pageerror.
  PDF được kiểm bằng Chromium đầy đủ và native plugin, không chỉ kiểm URL iframe.
- Lượt E2E đầu chọn nhầm scan thiếu OCR; đổi sang PDF kỹ thuật số cho bài viewer.
  Các lượt tiếp theo phát hiện query test trùng tên sau khi sửa và native PDF
  bị headless shell/guard chặn tài nguyên browser offline. Sửa locator đúng vùng,
  dùng channel chromium và cho phép đúng tài nguyên PDF browser/URL blob nội bộ;
  guard HTTP(S) ngoài localhost vẫn chặn. Không bỏ/skip assertion hay đổi code
  nghiệp vụ để che lỗi. Unit/Vitest đầu phát hiện rollback và nhãn form trùng,
  đã sửa và giữ regression.
- Dừng API qua stop file, fixture exit 0 và truy vấn PostgreSQL xác nhận **0** DB
  `hr_ats_test_t14_*` còn lại; web kiểm thử đã dừng. Không xoá DB dev/test/volume.
  Tự review theo secure-code-review: quyền từng tài nguyên/CSRF/whitelist, ORM
  parameter hoá, escape nội dung và log không có CV/note/comment; không có dữ
  liệu thật, secret, CV mới hoặc artifact kiểm thử được đưa vào diff.

ASSUMED: các mặc định nhỏ #59–#61 về DTO/quyền sửa, note chủ động và profile
correction giữ provenance bản CV. Không có blocker; email/interview/stage/task
đầy đủ theo T19–T25, quản trị đồng ý theo T29.

NOT TESTED: CI remote (chưa push), review độc lập và merge. Chờ `Review T15`;
chưa đổi trạng thái done. Không chạy seed T18 hoặc đánh giá lại mô hình vì T15
không sửa pipeline/chấm điểm/provider. File chính: API/schema/service profile,
test_profile.py; CandidateProfile/ProfileInfo/ProfileAI/CvPreview, profile-types,
API client blob, vi.ts và test UI/E2E; spec 02/03/05/08, open-questions, PROGRESS.

## T14 · 2026-11-08 · review

VERIFIED: triển khai theo `tasks/_implement.md` trên nhánh
`task/T14-job-detail-upload-ranking`; T12/T13 đã done và working tree sạch trước
khi bắt đầu. Giữ review đến khi được duyệt và merge vào main.

- Thêm GET bảng xếp hạng có quyền Job từ DB, phân trang 20/100, q literal và lọc
  stage/mức AI; mặc định mức AI rồi điểm giảm dần, null cuối, ngày/id ổn định.
  Query chỉ chọn cột tóm tắt, không lấy CV text/vector/liên hệ cho bảng. Bỏ hồ sơ
  đã xoá và ứng viên đã xoá/gộp/hết hạn. Counts bảy mức/trạng thái toàn Job trước
  filter/page; dùng chung cho JobResponse, batch một query nhóm cho trang Job.
- GET trạng thái CV giữ quyền/audit T07; thêm processing_error cố định và
  application_id/ai_status có kiểm quyền Job gốc, không xuất error DB. Đọc file
  thông qua Job khác không tiết lộ Application Job gốc. Upload SHA trùng giữ
  contract T07, không tự chuyển/thêm sang Job khác. HTTP polling thành công
  (health/file/ranking) xuống DEBUG, lỗi giữ INFO, chỉ route template.
- UI `/jobs/[id]` ba tab; Ứng viên có kéo thả/chọn nhiều file, tiến trình/lỗi riêng
  tên file, polling 3 giây, tìm/lọc, phân trang, bảng sáu cột không hiện điểm số,
  AiLevelBadge và thống kê. Trạng thái file dừng polling khi terminal/lỗi HTTP,
  retry riêng đúng dòng. Hỗ trợ tải lại file trùng từng lỗi, giới hạn 50 tệp và
  báo rõ trùng ở Job khác. Danh sách Job có cột counts và tên mở trang chi tiết.
- Dòng/nút tên mở Sheet khung, Escape/Đóng trả focus; Thông tin đọc mô tả/yêu cầu
  và link Sửa T13; Quy trình khung T20, chi tiết/feedback ở T15. Mọi chuỗi UI mới
  trong vi.ts. Không thêm mutation tuyển dụng, schema, dependency hay provider.
- Thêm fixture trình duyệt DB/storage dùng một lần, Alembic và FakeLLM/eager
  Celery; tài khoản ranking riêng cho E2E song song. Dừng bằng stop file để dọn
  graceful trên Windows. Cập nhật README, spec 03/05/08 và câu hỏi #55–#58.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Kéo 10 CV mẫu vào Job mẫu/FakeLLM, bảng hiện 10 dòng đúng thứ tự AI | VERIFIED — đạt | `test_ten_real_synthetic_cvs_ranked_with_independent_file_errors` qua HTTP/storage/extract/parse/ẩn danh/embedding/score thật trên PostgreSQL; Playwright `job-ranking.spec.ts` thực sự kéo bằng DataTransfer, kiểm 3 high → 1 medium → 6 low, sáu cột, filter/drawer/counts ở 1280px |
| File lỗi có thông báo Việt đúng dòng, file khác tiếp tục | VERIFIED — đạt | Cùng lô 10 CV + executable + PDF hỏng: API kiểm index/status/error an toàn; E2E kiểm lỗi trên dòng invalid.exe/broken.pdf, 10 file khác hoàn tất; Vitest kiểm ba trạng thái polling 3 giây, lỗi worker/AI/HTTP, retry và không phản chiếu lỗi thô |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, giữ volume dev.
- Backend: `uv sync`, `uv run alembic upgrade head`: pass, giữ head
  `0003_core_data_model`. Full suite cuối `uv run pytest`: **841 passed,
  12 skipped, 1 warning**, tổng 853 test, 175,45s. Skip chỉ OCR T08 do thiếu
  Tesseract trên Windows; warning upstream Starlette/httpx có sẵn. Không sửa
  test cũ, điều kiện skip hay tiêu chí. PostgreSQL/Redis local, FakeLLM/
  FakeEmbedder, fixture chặn mạng ngoài. Bộ T14 riêng **22 pass**; lượt chung
  `uv run pytest tests/api/test_ranking.py tests/api/test_cv_files.py -q --tb=short`
  sau tự review **39 pass**.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 120 file đúng
  format. `uv run mypy app`: pass, 71 source file. `git diff --check`: pass.
  Dùng UV_CACHE_DIR trong var; pytest cần quyền local cho tmp_path/cache Windows,
  lượt sandbox đầu báo PermissionError nên chạy lại có quyền, không đổi fixture.
- Frontend: `npm ci`: pass, 536 package, audit **0 vulnerabilities** (deprecation
  upstream giữ nguyên); `npm test`: **69 pass**, 9 file, không skip/mạng ngoài.
  `npm run lint`, `npm run typecheck`: pass. `NEXT_TELEMETRY_DISABLED=1 npm run build`
  (PowerShell đặt env trước): pass, có `/jobs/[id]`, 9,21 kB/159 kB first load JS.
- `uv run python -m tests.ranking_browser_server` + `npm run dev`, sau đó
  `npx playwright test`: **3 pass**, gồm hai bài auth T04. Lượt đầu hai bài dùng
  chung admin khiến phiên bị thu hồi/401; tách tài khoản fixture rồi cả suite
  pass. Vitest đầu bắt mất focus khi đóng drawer; sửa onCloseAutoFocus và giữ
  assertion. Đã xem ảnh `var/t14-ranking.png`, không tràn ở 1280px/pageerror.
- Dừng API bằng `var/t14-browser.stop`, process exit 0, web dừng sau E2E.
  `docker compose exec -T db psql -U hr -d postgres -tAc "SELECT count(*) FROM pg_database WHERE datname LIKE 'hr_ats_test_t14_%'"`
  trả **0**, không còn DB T14 tạm, giữ DB dev/test và volume. Ảnh/artifact trong
  var/test-results được gitignore.
- Tự review theo secure-code-review: endpoint → auth/quyền DB → SQL tham số →
  summary/snapshot công khai; kiểm thu hồi membership và file scope khác Job.
  Không SQL/path/shell từ input, không HTML thô, không log CV/tên file/query/lỗi
  provider. Test metadata chứng minh lỗi DB giả không bị phản chiếu. Không thay
  dependency backend; pip-audit không cài nên scanner Python NOT TESTED.

File chính: schemas/services/ranking.py, api/jobs.py, services/cv_files.py,
core/middleware.py, test_ranking.py, ranking_browser_server.py;
frontend job-detail/cv-upload/ai-counts/jobs-list, route jobs/[id], types/i18n,
Vitest và E2E job-ranking; README/specs/PROGRESS.

ASSUMED: #55–#57 ghi mặc định nhỏ, không blocker. VERIFIED: #58 là giới hạn fake
parse T09 với nhãn riêng dòng/header, UI hiển thị thiếu thông tin đúng contract;
không mở rộng parser ngoài T14. NOT TESTED: provider/dữ liệu thật, tải production,
OCR Windows, CI remote (chưa push), review độc lập. Chờ Review T14, CI và merge.

## T13 · 2026-11-08 · review

VERIFIED: triển khai theo `tasks/_implement.md` trên nhánh
`task/T13-hiring-units-jobs`; T05 đã done và working tree sạch trước khi bắt đầu.
Giữ review đến khi được duyệt và merge vào main.

- Thêm schema/service/router đơn vị tuyển và Job; list phân trang/tìm/lọc ngay
  trong SQL theo quyền owner/member từ DB, có tổng số đúng scope. Admin/lead quản
  lý đơn vị; recruiter chỉ nhận id/name qua `/jobs/options`, không có liên hệ
  hay quyền quản trị user. Chỉ admin/lead đổi owner Job; recruiter tạo cho mình.
- POST/PATCH lưu Job/vector/members nguyên tử, row lock khi sửa; PUT thay thành
  viên, bỏ trùng và kiểm active user. Giữ tham chiếu inactive cũ để vẫn sửa được
  Job; tham chiếu mới phải active. Không thêm migration/dependency/dịch vụ.
- Kiểm input theo cột DB, field thừa/null, lương và yêu cầu mở tuyển trên bản ghi
  đã ghép PATCH. Nối `embed_job` T11; lỗi rollback/503 an toàn. Cập nhật mốc mở/
  đóng khi chuyển trạng thái. Đổi yêu cầu có Application chưa xoá trả
  needs_rescore; không tự publish, đổi stage hoặc gửi email.
- Thay trang rỗng bằng bảng Job 6 cột, tìm/lọc/phân trang, form `/jobs/new` và
  `/jobs/[id]/edit`: hai ô yêu cầu mỗi dòng một tiêu chí, đơn vị/owner/members và
  thông tin tuyển dụng. Thiếu tiêu đề báo lỗi tiếng Việt và focus trường. Hộp
  chấm lại sau lưu dùng API T12 khi xác nhận; huỷ giữ điểm, queue lỗi cho thử lại.
- Cài đặt thêm tab Đơn vị tuyển cho admin/lead, form thêm/sửa và xác nhận ngừng
  hoạt động/kích hoạt; giữ tab Người dùng mặc định của admin theo T04. Mọi chuỗi
  UI mới nằm trong vi.ts; có tải/rỗng/lỗi/thử lại. Cột số ứng viên AI/chi tiết Job
  giữ ở T14. Cập nhật README, spec 03/05/07/08 và câu hỏi #52–#54.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| API: recruiter chỉ thấy Job của mình; tiêu đề bắt buộc, min ≤ max, ít nhất một must_have khi open | VERIFIED — đạt | `tests/api/test_jobs.py`: 45 test; owner/member/outsider, admin/lead, thu hồi membership, lọc/total/phân trang; title rỗng/whitespace/null/quá dài, lương âm/đảo/partial PATCH, draft→open thiếu yêu cầu và xoá yêu cầu cuối khi đang open |
| Vitest: thiếu tiêu đề báo lỗi tiếng Việt | VERIFIED — đạt | `job-form.test.tsx`: thiếu/rỗng/whitespace title, role=alert, focus title, không gửi request; thêm test lương/open, lưu member_ids nguyên tử, xác nhận/huỷ/retry rescore và lỗi tải/lưu. Toàn bộ frontend 59 pass |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, giữ các dịch vụ/volume dev.
- Tại backend: `uv sync`: pass, 125 package resolve/73 package mặc định; không
  đổi manifest/lock. Dùng `UV_CACHE_DIR=D:/code/tool/hr-ats/var/uv-cache` vì cache
  mặc định ngoài sandbox. `uv run alembic upgrade head`: pass, head giữ
  `0003_core_data_model`; suite migration DB trống/rollback/schema comparison pass.
- `uv run pytest`: **819 passed, 12 skipped, 1 warning**, tổng 831 test, 159,10s.
  Skip chỉ OCR T08 do Windows thiếu Tesseract, không thêm skip/giảm tiêu chí.
  Warning upstream Starlette/httpx giữ nguyên. FakeLLM/FakeEmbedder, PostgreSQL/
  Redis local thật, test chặn mạng ngoài. Lượt riêng T13 **45 passed**; lượt
  đầu sandbox có warning ghi cache, lượt full có quyền local không còn warning đó.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 116 file format
  đúng. `uv run mypy app`: pass, 69 source file. `git diff --check`: pass.
- Tại frontend: `npm ci`: pass, 536 package, audit **0 vulnerabilities**;
  deprecation ESLint/whatwg-encoding có sẵn, không đổi dependency. `npm test`:
  **59 passed**, 8 file, không skip, mock HTTP và không mạng ngoài. `npm run lint`,
  `npm run typecheck`: pass. Lượt đầu typecheck bắt `exact` không thuộc option
  Testing Library; bỏ option dư (name string đã exact mặc định), giữ assertion.
- `NEXT_TELEMETRY_DISABLED=1 npm run build` (PowerShell đặt env trước): pass,
  gồm `/jobs`, `/jobs/new`, `/jobs/[id]/edit`, `/settings`.
- `uv run python -m tests.auth_browser_server` + `npm run dev`, sau đó
  `npx playwright test`: **2 passed**, giữ nguyên E2E auth T04 với DB tạm riêng.
  `node ../var/t13-browser-smoke.mjs`: pass đơn vị→tạo/sửa/lọc Job, validation
  tiếng Việt/focus, recruiter member và thu hồi membership qua API thật, 6 cột,
  không tràn 1280px, không request ngoài localhost/pageerror. Đã xem ảnh local
  `var/t13-job-form.png`, `var/t13-jobs.png`. Lượt smoke đầu cần chờ navigation
  hoàn tất trước khi kiểm disabled owner; sửa script local rồi pass.
- Dừng web/API sau kiểm chứng; Ctrl+C từ runner Windows dừng process trước
  finally của fixture, đã dọn đúng DB mới bằng UUID Job riêng + prefix tạm + kiểm
  không có connection. Xác nhận không còn DB T04 tạm hay listener 3000/8000;
  giữ `hr_ats`, `hr_ats_test` và volume dev. Script/ảnh chỉ là artifact gitignore.
- Tự review theo secure-code-review: trace mọi endpoint → quyền DB/CSRF → ORM
  parameterized → schema công khai; search escape wildcard, không HTML thô,
  không PII/secret/provider exception vào log. Mutation không dùng body để cấp
  quyền trước kiểm; queue rescore chỉ sau HR xác nhận. npm audit 0; pip-audit
  NOT TESTED (không cài, không đổi dependency backend trong T13).

File chính: `backend/app/{api,schemas,services}/jobs.py`, permissions/main,
`backend/tests/api/test_jobs.py`, `frontend/src/components/{job-form,jobs-list,
hiring-units-settings,query-feedback}.tsx`, test form/units, routes jobs/settings,
job-types/api/i18n, README và các spec liên quan.

ASSUMED: #52–#54 ghi rõ quyền tạo/sửa, endpoint options, giới hạn input, mốc mở
lại, lưu members nguyên tử và mặc định tham chiếu inactive. Không có blocker.
NOT TESTED: provider/model thật, dữ liệu thật, tải production, CI remote
(chưa push), review độc lập; OCR thật giữ kiểm chứng T08/Linux/CI cũ, không sửa
extractor trong T13. Chờ Review T13, CI xanh và merge; chưa chuyển done.

## T12 · 2026-11-08 · review

VERIFIED: triển khai theo `tasks/_implement.md` trên nhánh
`task/T12-criteria-scoring`; T11 đã done và working tree sạch trước khi bắt đầu.
Giữ trạng thái review đến khi được duyệt và merge vào main.

- Thêm `ai/score.py`: dùng prompt score v1/adapter T09, chỉ nhận anonymized_text
  và yêu cầu Job. Kiểm đúng thứ tự/nguyên văn/kind/số tiêu chí; sai coverage trả
  lỗi an toàn. Bằng chứng so sau NFC/gộp khoảng trắng, phân biệt hoa/thường và
  dấu; bịa/null/không khớp → unknown, xoá evidence sai. Không thêm retry ngoài
  adapter, không đọc CV gốc/identity và không log output.
- Thêm `ai/scoring_rules.py`: công thức 75/25, met/partial/not_met/unknown theo
  spec; insufficient ưu tiên trước low/high/medium, ngưỡng 50% unknown, 300 ký tự
  và 75 điểm. Cấu hình SCORE_* qua môi trường, validate miền/NaN/Infinity. Trường
  hợp không must/không tiêu chí và round được ghi rõ tại spec 04/câu hỏi #49.
- Nối pipeline tạo Application new/owner Job cùng transaction Candidate/file,
  chỉ publish score sau commit. Revision dùng lại active Application, reset AI
  và giữ stage/owner. Unique partial index PostgreSQL chống hai insert cùng cặp;
  không thêm migration. SHA-256 và delivery file lặp giữ hành vi T07/T10.
- Worker score khoá hàng, savepoint bao score/activity ai_scored, metadata model/
  version/thời điểm; lỗi rollback/failed không chứa exception. Delivery lặp không
  chấm/ghi activity lại; crash rollback và delivery sau xử lý được. Bulk rescore
  transaction/publish từng hồ sơ, bỏ soft delete/merged/hết hạn, cô lập lỗi; thiếu
  anonymized_text failed, không fallback CV gốc. Không đổi stage/gửi email.
- Thêm ba POST theo T12 với schema input, ApplicationRead, cookie/CSRF và quyền
  Job owner/member từ DB, admin/lead toàn bộ. Create 201, trùng active 409,
  rescore 202, lỗi publish 503 hoặc snapshot create failed. Spec 03 ghi rõ
  contract và cách thử lại; publish lỗi không đổi CV done hay ghi đè score done.
- FakeLLM vẫn offline, chỉ đọc từ khoá/mục kỹ năng và số năm kinh nghiệm VI/EN,
  không đọc gold labels. Có nhưng thiếu kinh nghiệm → partial, không kinh nghiệm
  → not_met, đủ → met; trích evidence thật. Không sửa CV/nhãn/công thức/prompt.
- Thêm 83 test; mở rộng test upload T07 để giữ đủ ba cv_uploaded và kiểm thêm ba
  ai_scored/Application theo hành vi T12. Lượt full đầu phát hiện kỳ vọng cũ chỉ
  có ba activity; đã bổ sung assertion theo loại, giữ mọi kiểm tra upload/quyền/
  download/audit, không bỏ test hay giảm tiêu chí.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Mọi nhánh ai_level và công thức điểm | VERIFIED — đạt | `tests/unit/test_scoring_rules.py`: 31 test, gồm bốn mức, biên 299/300 ký tự, 50% unknown/75 điểm, thứ tự ưu tiên, thiếu nice/must/criteria, round và cấu hình; coverage module 100% dòng/nhánh |
| Evidence bịa → unknown | VERIFIED — đạt | `tests/unit/test_score.py`: 28 test, bịa/null/sai hoa thường cho cả bốn result, NFC/NFD/whitespace, coverage tiêu chí, factory và FakeLLM kinh nghiệm; coverage score.py 100% dòng/nhánh |
| E2E FakeLLM/jobs.json ≥70% expected_level | VERIFIED — đạt | `test_fake_llm_end_to_end_sample_jobs_matches_at_least_seventy_percent`: HTTP upload 50 PDF/DOCX thật giả lập → storage/extract/parse/ẩn danh/embedding → API tạo hồ sơ/worker/Postgres; 250/250 cặp đã chấm khớp, 250/300 toàn ma trận và 50/60 CV khớp cả năm Job = 83,3%. Tính 10 CV scan chưa chấm là không khớp, không loại khỏi mẫu số; kiểm có cả high/medium/low |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, giữ dịch vụ/volume dev hiện có.
- Tại backend: `uv sync`: pass, 125 package resolve/73 package mặc định được kiểm
  tra; manifest/lockfile không đổi. Sandbox chặn cache uv mặc định, dùng
  `UV_CACHE_DIR=D:/code/tool/hr-ats/var/uv-cache`; pytest dùng quyền local được
  cấp cho thư mục tạm/cache và DB, không thay fixture/chặn mạng.
- `uv run alembic upgrade head`: pass; schema/head vẫn `0003_core_data_model`.
  Suite migration DB trống/rollback/schema comparison tiếp tục pass.
- `uv run pytest`: lượt cuối **774 passed, 12 skipped, 1 warning**, 786 test;
  skip chỉ 12 OCR T08 do Windows không có Tesseract, giữ ngoại lệ cũ. PostgreSQL/
  Redis local thật, FakeLLM/FakeEmbedder, không mạng ngoài. Warning upstream
  Starlette/httpx đã biết được giữ nguyên.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 112 file format
  đúng; `uv run mypy app`: pass, 66 source file. `git diff --check`: pass.
- `uv run pytest tests/unit/test_scoring_rules.py tests/unit/test_score.py tests/api/test_scoring.py tests/api/test_cv_worker.py --cov=app.ai.score --cov=app.ai.scoring_rules --cov=app.services.applications --cov=app.api.applications --cov=app.workers.tasks --cov-report=term-missing --junitxml=../var/t12-tests.xml -o junit_family=legacy -q`:
  **87 passed**, coverage tổng dòng/nhánh **96%**; score/rules/API/service mới
  đều 100%, worker 91% (các nhánh T10 và nhánh Application biến mất giữa bulk).
  Báo cáo JUnit local xác nhận `250/250 evaluated; 250/300 total; 50/60 CVs match
  all five jobs`. Không đặt ngưỡng coverage mới.
- `docker run --rm --pull never --network none --mount type=bind,source=D:/code/tool/hr-ats,target=/workspace,readonly -w /workspace/backend -e PYTHONDONTWRITEBYTECODE=1 hr-ats-t08-ocr uv run --no-sync pytest tests/unit/test_scoring_rules.py tests/unit/test_score.py tests/unit/test_llm.py tests/unit/test_extract.py -q -o cache_dir=/tmp/t12-pytest-cache`:
  **242 passed/0 skipped**, gồm OCR thật, repo read-only, không tải image/model.
- Tự review theo secure-code-review: trace ba endpoint → quyền DB → unique index/
  transaction → publish → worker chỉ anonymized_text; không SQL/path/shell từ
  input, không PII/exception provider vào log/activity. Thử lỗi queue/provider/
  activity, rollback, hai insert/delivery đồng thời và crash trên DB riêng đều
  pass. Không thay dependency/migration/frontend/dữ liệu mẫu; scanner dependency
  `pip-audit` không cài, không thêm công cụ/mạng ngoài để quét trong task này.

File chính: `backend/app/ai/score.py`, `scoring_rules.py`, `llm.py`,
`backend/app/services/applications.py`, `backend/app/api/applications.py`,
`backend/app/schemas/applications.py`, `backend/app/workers/tasks.py`, config/main,
test scoring/worker/upload, `.env.example`, README, spec 01/03/04/08 và câu hỏi mở.

ASSUMED: mặc định nhỏ ở #49–#51. Chưa thêm outbox ngoài spec: crash giữa commit
và publish có thể còn pending, dùng rescore sau phục hồi; bulk delivery trùng có
thể mở lượt chấm lại mới. Chỉ kiểm evidence tồn tại, chưa kiểm hàm ý bằng LLM/NLI.
Không có blocker T12.

NOT TESTED: provider/model thật và dữ liệu thật, GitHub Actions trên remote (chưa
push), UI nghiệp vụ/E2E trình duyệt (T14/T18), bộ đánh giá chất lượng thật T31.
Không thay kết luận UNKNOWN trong LLM contract; tỷ lệ bộ giả không chứng minh
chất lượng model thật. Chờ Review T12, CI xanh và merge.

## T11 · 2026-11-08 · review

VERIFIED: triển khai theo `tasks/_implement.md` trên nhánh
`task/T11-anonymize-embeddings`; T10 đã done và working tree sạch trước khi bắt
đầu. Giữ review đến khi được duyệt và merge vào main.

- Thêm `ai/anonymize.py`: NFC, che liên hệ và tên có/không dấu/đ/hoa thường theo
  ranh giới từ; bỏ metadata cá nhân VI/EN, cả nhãn riêng dòng, link profile và
  markup ảnh. Giữ kỹ năng, công ty và mốc thời gian nghề nghiệp. Nếu parse không
  cung cấp tên khớp, che header có thể là tên mà không lưu identity suy đoán.
  Giới hạn heuristic được ghi rõ ở spec 04/câu hỏi #46, không tuyên bố NER đầy đủ.
- Thêm Protocol Embedder/factory, FakeEmbedder SHA-256 từng từ tất định và
  LocalEmbedder sentence-transformers lazy-load/cache process, trọng số ở
  `var/models`, tắt remote code/progress, dùng safetensors. Validate đủ batch,
  đúng chiều, hữu hạn, khác zero và chuẩn hoá L2; lỗi cố định, không log input
  hay exception gốc, không tự fallback fake. Test không tải model/mạng ngoài.
- Dependency local ở extra `local-embedding` (sentence-transformers 5.7.0
  trong uv.lock); `uv sync` mặc định vẫn giữ 73 package cho fake/CI. So TOML của
  lockfile với HEAD xác nhận mọi version dependency đã có đều giữ nguyên.
- Nối hook worker T10 bằng `services/embeddings.embed_candidate`: chỉ text đã
  ẩn danh được truyền embedder; text/vector cùng transaction với Candidate/file,
  lỗi rollback revision. Nghi trùng theo tên/cosine hoạt động, chỉ gợi ý UUID.
  `embed_job` lấy title/description/must_have/nice_to_have, không tự commit;
  T13 dùng hook này trước commit lúc tạo/sửa. Không mở API Job/tìm kiếm sớm.
- CLI `reembed --all` dùng text đã ẩn danh, không đọc CV gốc/gọi parse. Rebuild
  ứng viên còn hạn/chưa xoá/chưa gộp và mọi Job trong một transaction, clear
  vector ứng viên không hợp lệ. Thiếu text/lỗi/sai chiều rollback cả lượt;
  chỉ in số lượng/mã lỗi. README yêu cầu dừng writer/tìm kiếm lúc đổi model,
  đồng bộ cấu hình và chỉ bật lại sau thành công; dimension khác vẫn cần
  migration riêng. Sửa stdout UTF-8 để trợ giúp CLI chạy được trên Windows.
- Mở rộng test T10, thay kỳ vọng hook rỗng bằng kiểm tra vector/text thực tế;
  giữ và tăng các assertion cũ về liên hệ, dedupe, rollback, consent và quyền.
  Cập nhật README, spec 04/08 và câu hỏi #46–#48. Không đổi DB schema, API,
  frontend, stack, stage hoặc luồng gửi email.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Ẩn danh ít nhất 15 CV, không còn họ tên có/không dấu, email, SĐT, ngày sinh, giới tính | VERIFIED — đạt | `test_anonymize_fifty_extracted_cvs_and_name_variants`: 50 PDF/DOCX giả được extract thật, thêm biến thể tên uppercase/không dấu/NFD; kiểm mọi trường cá nhân và giữ skills/company/start. 22 test metadata/ranh giới/null-name bổ sung |
| Pipeline lưu embedding đúng chiều; top-k bằng FakeEmbedder chạy được | VERIFIED — đạt | Test upload 10 CV T10 ghi nhận input embedder chỉ có anonymized_text; vector đúng EMBEDDING_DIM. `test_t11_pipeline_cosine_top_k_and_real_duplicate_suggestion` truy vấn cosine top-2 PostgreSQL thật, kiểm thứ tự/gợi ý không gộp. Test sai chiều rollback revision |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, giữ dịch vụ/volume dev.
- Tại backend: `uv sync`: pass, resolve 125 package, kiểm tra 73 package mặc
  định; không cài extra nặng/tải trọng số model. `uv run alembic upgrade head`:
  pass, head vẫn `0003_core_data_model`; suite migration từ DB trống/rollback/
  schema comparison cũ tiếp tục pass.
- `uv run pytest`: lượt cuối **691 passed, 12 skipped, 1 warning**, 703 test
  thu thập (tăng 105 test so với T10). Skip chỉ là 12 OCR T08 vì Windows không
  có Tesseract; không thêm skip/giảm điều kiện. PostgreSQL/Redis local thật;
  CLI subprocess `python -m app.scripts.reembed --all` chạy trên DB tạm đã
  migrate và commit vector khớp kết quả FakeEmbedder của process cha.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 104 file format
  đúng; `uv run mypy app`: pass, 61 source file. CLI `uv run python -m
  app.scripts.reembed --help`: pass; regression subprocess ép cp1252 vẫn pass.
- `uv run pytest tests/unit/test_anonymize.py tests/unit/test_embed.py tests/unit/test_reembed_cli.py tests/api/test_embeddings.py tests/api/test_cv_pipeline.py --cov=app.ai.anonymize --cov=app.ai.embed --cov=app.services.embeddings --cov=app.scripts.reembed --cov-report=term-missing -q`:
  **124 passed**, coverage dòng/nhánh **96%** (anonymize 98%, embed 100%, hooks
  100%, CLI 89%; entrypoint/session CLI chạy trong subprocess riêng nên không
  cộng vào coverage process cha). Không đặt ngưỡng coverage mới.
- Linux image OCR T08 có sẵn, repo read-only, network none:
  `docker run --rm --network none --mount type=bind,source=D:/code/tool/hr-ats,target=/workspace,readonly -w /workspace/backend -e PYTHONDONTWRITEBYTECODE=1 -e COVERAGE_FILE=/tmp/t11-linux.coverage hr-ats-t08-ocr uv run --no-sync pytest tests/unit/test_anonymize.py tests/unit/test_embed.py tests/unit/test_extract.py tests/unit/test_redact.py -q -o cache_dir=/tmp/t11-pytest-cache`:
  **212 passed/0 skipped**, gồm OCR thật. Cùng image/mount/network chạy
  `uv run --no-sync pytest tests/unit/test_reembed_cli.py -q -o cache_dir=/tmp/t11-cli-pytest-cache`:
  **4 passed/0 skipped**. `uv run --no-sync mypy --cache-dir=/tmp/t11-mypy-cache app`:
  pass 61 file trên Linux. Các lượt Linux kiểm đúng bản app cuối.
- `git diff --check`: pass. Tự review theo secure-code-review: trace CV → che
  cục bộ → embedder → parameterized SQL; không input CV vào path/model download,
  không log CV/liên hệ/provider exception, không mở thêm endpoint/quyền. Không
  còn finding đã xác nhận trong phạm vi T11. Dependency vulnerability audit
  NOT TESTED vì không có pip-audit; không cài thêm công cụ ngoài task. Cảnh báo
  Starlette/httpx #13 có sẵn được giữ nguyên.

File chính: `backend/app/ai/{anonymize,embed}.py`,
`backend/app/services/embeddings.py`, `backend/app/workers/tasks.py`,
`backend/app/scripts/reembed.py`, `backend/tests/unit/test_{anonymize,embed,reembed_cli}.py`,
`backend/tests/api/test_{embeddings,cv_pipeline}.py`, manifest/lockfile, README,
spec 04/08, open-questions và PROGRESS.

ASSUMED: mặc định #46–#48 đã ghi rõ. NOT TESTED: model local BAAI/bge-m3 thật,
chất lượng retrieval thực tế, tải lớn/rebuild toàn kho production, CI remote
(chưa push), review độc lập. Không đổi frontend nên không chạy frontend/E2E UI.
Điều kiện dữ liệu thật/provider parse tại #40 vẫn UNKNOWN trước production.
Chờ Review T11, CI xanh và merge; T12/T13/T16 nối chức năng trong task của chúng.

## T10 · 2026-11-08 · review

VERIFIED: triển khai theo `tasks/_implement.md` trên nhánh
`task/T10-parse-dedupe-pipeline`; T07/T08/T09 đã done và working tree sạch trước
khi bắt đầu. Giữ review đến khi được duyệt và merge, chưa chuyển done.

- Thêm `ai/parse.py`: render ba prompt T09 cùng version, gọi bằng
  ThreadPoolExecutor ba thread, gộp `ParsedCV` và trả model/prompt_version.
  Không đưa session DB vào thread, không nhân thêm retry; một phần lỗi thì
  không trả parse thiếu phần. `ParseResult` không hiện nội dung trong repr.
- Thêm `services/dedupe.py`: email lowercase, phone canonical từ redaction
  cục bộ; xét mọi liên hệ, khớp nhiều người thì failed để kiểm tra thủ công.
  Advisory transaction lock chung nối tìm + ghi, tránh hai file khác hash cùng
  người tạo hai Candidate. Bỏ bản ghi đã xoá/đã gộp, giữ thông tin cũ khi field
  mới null/mảng rỗng, cập nhật dữ liệu mới có giá trị, không tự sinh consent.
- Worker thật đọc storage → extract → che liên hệ → parse → ghi Candidate/file
  và metadata → hook T11/T12 → done. Row lock và savepoint giữ thao tác nguyên tử;
  lỗi từng bước rollback dữ liệu dở rồi lưu failed/lỗi Việt cố định, không ghi
  exception gốc. Delivery done/failed bỏ qua; crash rollback để redelivery tiếp
  tục. `running` chỉ flush nên reader có thể thấy pending đến khi commit.
- Retention tính ngày theo TZ, cộng DATA_RETENTION_MONTHS tháng lịch dương,
  xử lý cuối tháng/năm nhuận. Tên thiếu giữ null trong parsed_json, Candidate dùng
  nhãn Chưa xác định. Hook ẩn danh/embedding/application/chấm điểm vẫn rỗng đúng
  phạm vi T10; không đổi stage hay gửi email. Khi hook T11 có vector, CV không
  liên hệ được xét tên chuẩn hoá + cosine > 0.95; chỉ ghi UUID gợi ý vào
  `parsed_json.possible_duplicate_of`, không tự gộp.
- Sửa quyền phát sinh từ việc gắn Candidate: uploader vẫn đọc đúng file riêng
  không gắn Job sau parse; không mở file khác cùng người hoặc vượt scope Job.
  Spec 03/04/07/08, README và câu hỏi #41–#45 mô tả contract/default này.
  Không thêm dependency, migration/schema DB, dịch vụ hoặc frontend.
- Bộ test T07 vẫn giữ mọi assertion; fixture upload/quyền cung cấp kết quả extract
  giả rõ ràng vì có ảnh trắng 10px/PDF ngắn dùng để test storage/queue. Test worker
  đồng thời dùng PDF giả đầy đủ thay fixture ngắn, storage và DB kết nối độc lập.
  Các test pipeline T10 mới dùng PDF/DOCX thật từ bộ giả đã commit, không mock
  extract. Toàn bộ test chặn mạng ngoài, chỉ FakeLLM/DB local/OCR local.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Upload 10 CV mẫu → 10 ứng viên, email/SĐT đúng nhãn | VERIFIED — đạt | `test_upload_ten_labeled_cvs_dedupe_cross_format_and_isolate_corruption`: HTTP upload 10 PDF/DOCX giả → local storage → extract thật → FakeLLM → PostgreSQL; đối chiếu đủ 10 nhãn và phone +84; kiểm metadata/retention/không sinh consent, liên hệ không vào ba request parse hoặc log INFO |
| CV khác định dạng cùng email không tạo ứng viên mới | VERIFIED — đạt | Cùng test: PDF đầu → DOCX mới cùng email viết hoa, cùng candidate_id và vẫn 10 người, cập nhật chức danh/kỹ năng/kinh nghiệm; thêm test phone-only canonical, giữ field/consent cũ và SHA-256/delivery lặp không parse lại |
| Một file hỏng chỉ file đó failed | VERIFIED — đạt | PDF hỏng đặt giữa lô 11 file: đúng một failed, 10 done. Bảy test lỗi từng bước, lỗi constraint DB/LLM/OCR, rollback revision và identity conflict không để Candidate dở hoặc ảnh hưởng file tiếp theo |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass; giữ dịch vụ/volume dev có sẵn.
- Tại backend: `uv sync`: pass, 74 package resolve/73 package kiểm tra;
  manifest/lockfile không đổi. `uv run alembic upgrade head`: pass, head vẫn
  `0003_core_data_model`; test DB trống/rollback/schema comparison cũ vẫn pass.
- `uv run pytest`: lượt cuối **586 passed, 12 skipped, 1 warning** (598 thu thập,
  tăng 43 test so với T09). 12 skip chỉ là OCR T08 do Windows không có Tesseract;
  không thêm skip hoặc giảm điều kiện test. Bao gồm test hai upload trùng hash,
  hai file khác hash cùng liên hệ, hai delivery pending cùng ID chỉ parse một lần,
  crash/redelivery trên DB tạm đã migrate với commit/kết nối PostgreSQL thật.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 96 file đã format;
  `uv run mypy app`: pass, 57 source file.
- `uv run pytest tests/unit/test_parse.py tests/unit/test_cv_retention.py tests/api/test_dedupe.py tests/api/test_cv_pipeline.py tests/api/test_cv_worker.py --cov=app.ai.parse --cov=app.services.dedupe --cov=app.workers.tasks --cov-report=term-missing -q`:
  **43 passed**, coverage dòng/nhánh **99%** (parse 100%, dedupe 100%, worker 98%).
  Sau lượt đo bổ sung test identity conflict qua pipeline và siết capture INFO;
  toàn bộ có trong lượt full suite cuối trên. Không đặt ngưỡng coverage mới.
- Linux image OCR T08 đã có, không tải dependency, repo chỉ đọc/mạng tắt:
  `docker run --rm --network none --mount type=bind,source=D:/code/tool/hr-ats,target=/workspace,readonly -w /workspace/backend -e PYTHONDONTWRITEBYTECODE=1 -e COVERAGE_FILE=/tmp/t10-linux.coverage hr-ats-t08-ocr uv run --no-sync pytest tests/unit/test_parse.py tests/unit/test_cv_retention.py tests/unit/test_extract.py tests/unit/test_redact.py -q -o cache_dir=/tmp/t10-pytest-cache`:
  **134 passed/0 skipped**, gồm OCR thật trên 10 scan và hai ảnh T08.
  Cùng image/network/mount: `uv run --no-sync mypy --cache-dir=/tmp/t10-mypy-cache app`
  pass 57 file trên Linux. Mã app giữ nguyên sau các lượt Linux này.
- `git diff --check`: pass. Tự review theo secure-code-review: trace byte/CV qua
  storage/extract → redaction → JSON parse → query parameterized; không log CV,
  liên hệ, provider/DB exception; không shell/fetch từ input; quyền file sau parse
  có test hai recruiter không đọc chéo. Không còn finding đã xác nhận trong phạm
  vi T10. Dependency không đổi; audit vulnerability riêng NOT TESTED (môi trường
  không có pip-audit). Cảnh báo Starlette/httpx #13 giữ nguyên.
- Sandbox ban đầu chặn ghi git ref, cache uv và Docker pipe; chạy lại thao tác
  cần thiết qua quyền công cụ được cấp rồi pass, không sửa fixture để né quyền.

File chính: `backend/app/ai/{parse,schemas}.py`, `backend/app/services/dedupe.py`,
`backend/app/workers/tasks.py`, `backend/app/core/{config,permissions}.py`,
`backend/tests/{unit/test_parse,unit/test_cv_retention,api/test_dedupe,api/test_cv_pipeline,api/test_cv_worker}.py`,
spec 03/04/07/08, open-questions, README và PROGRESS.

ASSUMED: mặc định #41–#45 đã ghi rõ. NOT TESTED: provider/model/key thật, tải lớn,
CI remote (chưa push), review độc lập. Không đổi frontend nên không chạy lại
frontend/E2E UI. Chính sách parse dữ liệu thật/provider ở #40 vẫn UNKNOWN trước
production; toàn bộ nghiệm thu T10 dùng dữ liệu giả. Việc T11/T12 nối hook thuộc
task tiếp theo, không chặn tiêu chí T10. Chờ Review T10, CI xanh và merge.

## T09 · 2026-11-08 · review

VERIFIED: triển khai theo `tasks/_implement.md` trên nhánh
`task/T09-llm-adapters-prompts`; T02 đã done, working tree sạch trước khi bắt đầu.
Hoàn thành triển khai, giữ review đến khi được duyệt và merge vào main.

- Thêm Protocol LLMClient.complete_json và factory từ Settings; FakeLLM,
  AnthropicLLM, OpenAILLM, OllamaLLM dùng HTTPX/Jinja2/Pydantic đã có trong stack.
  Không thêm SDK, dependency, dịch vụ, schema DB, API, UI hoặc logic T10/T12.
  Model thật phải cấu hình tường minh, cloud cần key; fake dùng fake-v1.
- Request JSON schema theo từng provider, timeout 60 giây mỗi pha, tối đa 4096
  token đầu ra. Retry mạng/429/5xx hai lần với backoff 1/2 giây; không theo redirect,
  lỗi 4xx/refusal/truncated/envelope fail an toàn. JSON/schema sai gọi lại đúng một
  lần, chỉ gửi mã lỗi Pydantic, không echo rejected output/loc/message/input/context.
  Tối đa sáu request khi kết hợp hai cơ chế; AppError tiếng Việt cố định.
- Log chỉ provider/model cấu hình, token/duration/outcome/lượt thử, không prompt,
  CV, output, credential hoặc lỗi thô. Token thiếu là null, không giả số liệu.
  Client đóng sau request; key SecretStr; endpoint cloud cố định, Ollama chỉ origin
  từ cấu hình máy chủ, không URL trong CV hay credential/path/query/fragment.
- Schema strict/extra forbid cho ba parse và score; scalar thiếu null, list [],
  tháng YYYY-MM hợp lệ, số năm hữu hạn không âm, kỹ năng chuẩn hoá/bỏ trùng;
  enum tiêu chí/cờ đóng, 2–3 lý do, evidence tối đa 20 từ. Kiểm evidence theo nguồn,
  tiêu chí đầy đủ và tính điểm thuộc T12; không nhận quyết định tuyển từ LLM.
- Loader frontmatter scalar/version/task/description, Jinja2 sandbox/StrictUndefined,
  giới hạn path trong prompts. Bốn prompt tiếng Việt v1: basic/experience/skills
  và score; user JSON qua tojson, CV/Job là dữ liệu không đáng tin cậy, không render
  lại nội dung thành template. Fake trích dòng có nhãn, score bằng cụm từ trong
  CV với ranh giới từ, case/accent-insensitive; không tìm trong JD hoặc suy luận
  kinh nghiệm/học vấn. CLI smoke dùng dữ liệu giả cố định, chỉ in metadata.
- README hướng dẫn smoke fake/cloud/local; spec 04/08 và câu hỏi #37–#40 mô tả
  contract/default/ràng buộc. Nhà cung cấp/model được duyệt vẫn UNKNOWN; không gửi
  CV thật. Chênh lệch chính sách che tên trước parse giữa llm-contract/spec 04 đã
  ghi #40, cần chốt trước production, không chặn các tiêu chí offline T09.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Factory chọn đúng adapter; fake hợp schema; schema sai retry rồi lỗi; log không có input | VERIFIED — đạt | 136 test mới trong test_llm.py/test_prompts.py/test_ai_schemas.py: đủ bốn factory/environment; parse/score với prompt thật tất định; HTTPX MockTransport ba provider kiểm hợp đồng, sửa một lần thành công/thất bại, backoff và trần sáu request; sentinel input/output/key không có trong log hay lỗi, kể cả chưa gắn PiiFilter |
| Có script `uv run python -m app.scripts.llm_smoke --provider anthropic` để tự thử key thật | VERIFIED — đạt | Module CLI và README; lệnh --provider fake thực tế exit 0/status ok cho bốn tác vụ. Test --provider anthropic qua HTTP mock đủ bốn tác vụ; thiếu key exit 1 với mã lỗi cố định, không nối mạng |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, giữ dịch vụ/volume dev có sẵn.
- `uv sync`: pass, 74 package resolve/73 package kiểm tra, manifest/lockfile không đổi.
- `uv run alembic upgrade head`: pass, head giữ 0003_core_data_model; test migration
  DB trống/rollback/schema comparison của bộ cũ vẫn pass.
- `uv run pytest`: lượt cuối **543 passed, 12 skipped, 1 warning** (555 thu thập),
  gồm **136 test T09**. 12 skip chỉ là OCR T08 vì Windows không có Tesseract, theo
  ngoại lệ task đó; không thêm skip hoặc sửa test cũ. PostgreSQL/Redis local thật,
  provider fake hoặc HTTP mock, fixture chung chặn mạng ngoài.
- `uv run pytest tests/unit/test_ai_schemas.py tests/unit/test_prompts.py tests/unit/test_llm.py --cov=app.ai.llm --cov=app.ai.prompts --cov=app.ai.schemas --cov=app.scripts.llm_smoke --cov-report=term-missing -q`:
  **136 passed**, coverage dòng/nhánh tổng **93%** (llm 92%, prompts 97%, schemas
  96%, smoke 86%); không đặt ngưỡng coverage mới.
- Linux dùng image OCR T08 đã có, không tải image/dependency:
  `docker run --rm --network none --mount type=bind,source=D:/code/tool/hr-ats,target=/workspace,readonly -w /workspace/backend -e PYTHONDONTWRITEBYTECODE=1 -e COVERAGE_FILE=/tmp/t09.coverage hr-ats-t08-ocr uv run --no-sync pytest tests/unit/test_ai_schemas.py tests/unit/test_prompts.py tests/unit/test_llm.py tests/unit/test_extract.py tests/unit/test_redact.py -q -o cache_dir=/tmp/t09-pytest-cache`:
  **257 passed/0 skipped**, gồm toàn bộ T09 và OCR T08 thật, repo chỉ đọc/mạng tắt.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 90 file đã format;
  `uv run mypy app`: pass, 55 file. Hai lệnh Ruff cho `../eval` cũng pass (4 file).
- `uv run python -m app.scripts.llm_smoke --provider fake`: exit 0, status ok,
  model fake-v1, prompt v1 và đủ bốn tác vụ, không CV/output.
- Lượt trung gian phát hiện missing Jinja variable qua tojson ném TypeError;
  sửa thành PromptError an toàn. Tự review phát hiện regex fake ăn dòng tiếp khi
  nhãn trống: test tái hiện fail trước sửa, đổi sang khoảng trắng ngang/cùng dòng,
  giữ test hồi quy; lượt full suite cuối trên đã pass sau sửa.
- Sandbox ban đầu chặn cache uv/temp pytest và Docker pipe. Thử cache trong var
  vẫn bị ACL temp, sau đó chạy lệnh chuẩn với quyền công cụ được cấp: pass; không
  bỏ test hoặc sửa fixture để tránh lỗi quyền. Artifact thử cache/temp thuộc var
  được gitignore; không có CV thật/secret trong thay đổi.
- Tự review theo secure-code-review: trace prompt/CV → JSON request → validation,
  lỗi/provider output không vào log/repair message; Jinja input không thực thi;
  endpoint không lấy từ CV, redirect tắt; không DB/email/stage/side effect. Không
  còn finding đã xác nhận trong phạm vi T09; không thêm dependency nên không có
  license mới. Quét dependency vulnerability riêng NOT TESTED (không có pip-audit).

File chính: `backend/app/ai/{llm,prompts,schemas}.py`,
`backend/app/scripts/llm_smoke.py`, `backend/tests/unit/test_{llm,prompts,ai_schemas}.py`,
`prompts/{parse_cv_basic,parse_cv_experience,parse_cv_skills,score_cv}/v1.md`,
README, spec 04/08, open-questions và PROGRESS.

ASSUMED: các mặc định #37–#40 đã ghi rõ. NOT TESTED: provider/model/key thật,
chất lượng LLM production/bias/eval T31, CI remote (chưa push), review độc lập.
Không đổi frontend nên không chạy lại frontend/E2E. Cảnh báo upstream
Starlette/httpx #13 giữ nguyên. Chờ Review T09, CI xanh và merge; chưa chuyển done.

## T08 · 2026-11-08 · review · Fix round 1

VERIFIED: đọc `tasks/reviews/T08.md` (APPROVE), thực hiện `tasks/_fix.md` trên nhánh
T08. `gh run view 42471694355 --log-failed` phát hiện attempt 1 lỗi HTTP 504 khi tải
uv; chạy lại job bằng `gh run rerun 42471694355 --failed` qua setup nhưng attempt 2
lộ lỗi mypy Linux: `subprocess.CREATE_NO_WINDOW` không có trên nền tảng đó.

Sửa `backend/app/ai/extract.py` dùng nhánh `if sys.platform == "win32"` được mypy
nhận diện, giữ cửa sổ OCR ẩn trên Windows và `creationflags=0` trên Linux. Tái hiện
lỗi bằng mypy Linux offline trước sửa; sau sửa mypy Linux/Windows đều pass 51 file.
Không bỏ kiểm tra type hay thay test. `uv sync --frozen`, migration và Ruff cho
backend/eval pass; backend Windows **407 passed/12 skipped** (không có Tesseract), chạy
lại test T08 sau sửa **109 passed/12 skipped**. Container offline có Tesseract thật
chạy **121 passed/0 skipped** sau sửa. Cảnh báo Starlette/httpx #13 giữ nguyên.

VERIFIED: [CI commit 7308023](https://github.com/khoavd18/hr-ats/actions/runs/42472261837)
đã xanh cả backend/frontend. Backend **419 passed/0 skipped**, gồm OCR thật;
lint/typecheck/migration pass. Frontend lint/typecheck/test/build pass. Chi tiết
CI-1/CI-2 và quyết định từng finding F1/F2, lệnh kiểm chứng, ngoại lệ cache Windows:
`tasks/reviews/T08.md`, mục Fix round 1. Giữ trạng thái `review` vì chưa merge.

## T08 · 2026-11-08 · review

VERIFIED: triển khai đúng T08 theo `tasks/_implement.md` trên nhánh `task/T08-text-extraction-redaction`; T02/T06 đã `done`, working tree sạch trước khi bắt đầu. Hoàn thành phần triển khai, giữ `review` đến khi được duyệt và merge vào main.

- Thêm `app/ai/extract.py`: `ExtractResult(text, method, page_count)` dùng enum DB sẵn có. PDF lấy block/line/span bằng PyMuPDF, tìm gutter hình học trái → phải, giữ heading/footer bắc cột và tách block bị MuPDF gộp giữa cột. DOCX giữ thứ tự paragraph/bảng, gồm bảng lồng, ô merge không lặp và header/footer. Chuẩn hoá NFC, gộp khoảng trắng, giữ xuống dòng. DOCX không có bộ phân trang nên trả page_count=None, PDF số trang thật, ảnh 1.
- Trang PDF dưới 50 ký tự render 300 DPI; ảnh JPEG/PNG dùng OCR local, xoay EXIF và flatten alpha lên nền trắng. Grayscale + median 3×3 giảm nhiễu scan. Tesseract nhận PNG qua stdin, trả text qua stdout; argv không có CV, không shell/file CV tạm, không log text/stderr, timeout hữu hạn. Thiếu executable báo đúng "Máy chủ chưa cài OCR"; OCR tắt/timeout/lỗi ngôn ngữ/file hỏng/rỗng có lỗi tiếng Việt bắt được. Caller T10 lưu trạng thái failed; chưa nối pipeline vào worker placeholder T07.
- Tái sử dụng validation magic/MIME, giới hạn 10 MiB và kiểm ZIP/macro của T07 trước parse. Giới hạn 100 trang PDF/25 triệu pixel cho ảnh hoặc trang OCR, từ chối PDF mã hoá. Các lỗi parser/OCR không phản chiếu exception gốc; text không xuất trong repr của kết quả.
- Thêm `app/ai/redact.py`: thay mọi email/SĐT bằng `[EMAIL]`/`[PHONE]`, trả email nguyên dạng và phone canonical theo thứ tự đầu tiên, bỏ trùng trong danh sách. Nhận 0/+84/0084, trunk 0, dấu cách/chấm/gạch/ngoặc, số quốc tế +/00; VN chuẩn hoá +84. Giữ ngày/tháng, số ngắn, phiên bản kỹ năng, không nối số qua xuống dòng. Chỉ che liên hệ; ẩn danh đầy đủ thuộc T11.
- README có cài Tesseract Windows UB Mannheim + vie/eng, PATH và Docker apt; CI cài engine/vie (eng là dependency) trước pytest. Cập nhật spec 04/08 và mặc định #34–#36; không thêm dependency Python, schema/migration/API/UI/KPI hoặc dịch vụ mới, không sửa skill thư viện.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| CV hai cột không trộn dòng, DOCX bảng lấy được kỹ năng, scan trích email khi có Tesseract | VERIFIED — đạt | `test_extract_committed_digital_cvs_against_labels` trên toàn bộ 50 CV kỹ thuật số: nội dung và liên hệ/kỹ năng đúng nhãn; hai cột theo thứ tự email → skills → profile → experience → education. Test heading/footer và thứ tự insert xáo trộn bắt lỗi MuPDF gộp block. 10 PDF scan cùng hai ảnh PNG/JPEG trích đúng email nhãn bằng Tesseract 5.3.0 vie+eng trong container Linux tắt mạng, không skip |
| Redact ít nhất 12 dạng SĐT/email, không còn chuỗi gốc | VERIFIED — đạt | 21 dạng SĐT + 8 dạng email trong `test_redact.py`, thêm bỏ trùng/idempotence/ngày/phiên bản/ranh giới và liên hệ liền nhau. So toàn bộ 50 CV kỹ thuật số extract → redact với email/phone nhãn; 10 scan cũng kiểm email đã che. Phone Việt Nam canonical +84, quốc tế giữ country code |

### Lệnh kiểm chứng

- `docker compose up -d db redis mailpit`: pass, giữ các dịch vụ/volume dev sẵn có.
- `uv sync` tại backend: pass, 74 package resolve/73 package kiểm tra, không đổi manifest/lockfile. `uv run alembic upgrade head`: pass; không đổi migration, head vẫn `0003_core_data_model`. Bộ migration trên DB trống/schema comparison trong pytest vẫn pass.
- `uv run pytest`: **407 passed, 12 skipped, 1 warning**, 419 test thu thập. 12 skip là test OCR thật vì Windows không có executable Tesseract, đúng ngoại lệ T08; không skip/xoá test cũ. Gồm 298 test cũ vẫn pass, 109 test T08 không cần executable. PostgreSQL/Redis local thật, provider fake và fixture chặn mạng ngoài.
- Chuẩn bị image kiểm thử `hr-ats-t08-ocr` từ image uv/Python 3.12 có sẵn, chỉ copy manifest/lockfile và cài engine vie/eng/dependency (giai đoạn chuẩn bị có mạng). Dockerfile/script thăm dò ở `var/t08-ocr-build/`, `var/t08-ocr-probe.py` được gitignore; không thêm service/image triển khai vào repo.
- `docker run --rm --network none --mount type=bind,source=D:/code/tool/hr-ats,target=/workspace,readonly -w /workspace/backend -e PYTHONDONTWRITEBYTECODE=1 -e COVERAGE_FILE=/tmp/t08.coverage hr-ats-t08-ocr uv run --no-sync pytest tests/unit/test_extract.py tests/unit/test_redact.py -q -o cache_dir=/tmp/pytest-cache --cov=app.ai --cov-report=term-missing`: **121 passed, 1 warning**, không skip; Tesseract 5.3.0, Python 3.12.12, repo chỉ đọc, container không có mạng. Coverage dòng/nhánh phần mới: tổng **95%**, extract **94%**, redact **100%**; không đặt ngưỡng coverage mới.
- `uv run ruff check .`, `uv run ruff format --check .`: pass, 83 file đã format. `uv run mypy app`: pass, 51 source file. `uv run ruff check ../eval`, `uv run ruff format --check ../eval`: pass, 4 file; fixture/generator không đổi.
- Các lượt trung gian: test mới phát hiện MuPDF gộp cột, đã sửa và giữ regression; kỳ vọng pixel ban đầu dùng round đã chỉnh thành ceil theo kích thước raster 300 DPI. OCR thật đầu tiên có ba email không khớp do nhiễu; thử các tiền xử lý ảnh local trên scan giả, median 3×3 giải quyết cả ba. Không thay nhãn, giảm điều kiện so email, bỏ test hoặc đoán ký tự từ fixture; bộ 121 test trên pass sau sửa.
- Tự review diff theo `secure-code-review`: byte từ caller qua validation → parser → text cục bộ hoặc stdin OCR; không gửi mạng, truy vấn DB hay ghi file CV tạm. Ngôn ngữ dùng danh sách argv và regex giới hạn, lỗi/provider stderr được thay thông báo cố định, xử lý từng file không giữ lỗi thô. Toàn bộ dữ liệu test là giả. Không còn finding đã xác nhận chưa xử lý trong phạm vi T08; không thêm dependency nên không đổi bề mặt license. Audit lỗ hổng dependency riêng chưa chạy (chưa có pip-audit trong manifest).

File chính: `backend/app/ai/{__init__,extract,redact}.py`, `backend/tests/unit/test_{extract,redact}.py`, `.github/workflows/ci.yml`, README, spec 04/08, open-questions, PROGRESS.

ASSUMED: các mặc định #34–#36 đã ghi rõ, không có blocker. NOT TESTED: CI remote (chưa push), review độc lập, installer Windows, mọi bố cục/ngôn ngữ ngoài bộ giả và OCR production. Regex chưa hỗ trợ email quốc tế hoá hoặc email bị OCR tách; heuristic cột chưa bảo đảm mọi CV thực tế. Không đổi frontend nên không chạy lại frontend/E2E. Cảnh báo upstream Starlette/httpx giữ nguyên theo #13, không tắt. Chờ `Review T08`, CI xanh và merge; chưa chuyển task sang `done`.

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

## T17 · 2026-11-09 · review

VERIFIED: Triển khai T17 trên nhánh `task/T17-excel-export-audit`; T14 đã done và working tree sạch khi bắt đầu. Migration 0004 thêm `audit_log.details` JSONB `NOT NULL DEFAULT '{}'`. Service audit dùng chung cho xem CV, tải CV, xem hồ sơ và export; caller commit cùng transaction.

- `GET /jobs/{id}/export.xlsx` kiểm scope Job từ DB, lấy hồ sơ còn hiệu lực theo thứ tự T14, tạo workbook tiếng Việt gồm họ tên/liên hệ/AI/điểm/lý do/kỹ năng/kinh nghiệm/stage/ngày nhận. Có header đậm, freeze hàng đầu, độ rộng cột, tên file theo slug + ngày, `no-store`; văn bản do người dùng cung cấp được ghi dạng text để tránh Excel formula injection.
- Audit export ghi `candidate.export`, entity Job và details chỉ gồm `record_count`, `job_id`; không có PII hay filter. Nút tab Ứng viên hiển thị cảnh báo trước, nhận blob và tải đúng tên file; chuỗi mới ở `frontend/src/i18n/vi.ts`.
- Cập nhật contract T17 trong spec 03 và test strategy spec 08. Test API mới đọc workbook bằng openpyxl, kiểm số dòng, Unicode, formula safety và audit. Vitest mới kiểm xác nhận và tải blob.

### Tiêu chí nghiệm thu

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Workbook mở được, đúng số dòng và tiếng Việt | INFERRED — test đã viết nhưng chưa chạy | `backend/tests/api/test_export.py`; backend pytest không kết nối được PostgreSQL |
| Audit `candidate.export` có record_count | INFERRED — test đã viết nhưng chưa chạy | Test kiểm details gồm `record_count`, `job_id`, không PII; runtime API chưa chạy được |
| Nút xuất có xác nhận dữ liệu cá nhân | INFERRED — test đã viết nhưng chưa chạy | Vitest T17 trong `job-detail.test.tsx`; tiến trình Vitest không hoàn tất |

### Lệnh và kết quả

- `uv run ruff check .`: VERIFIED — pass.
- `uv run ruff format --check .`: VERIFIED — 131 files đúng format.
- `uv run mypy app`: VERIFIED — 78 source files, không lỗi.
- `uv run alembic upgrade head --sql`: VERIFIED — sinh SQL tới revision `0004_audit_details`, có ALTER TABLE JSONB/default/not-null.
- `uv run alembic upgrade head`: NOT TESTED — PostgreSQL localhost không kết nối. `docker compose up -d db redis mailpit` không kết nối được Docker Desktop engine (named pipe `dockerDesktopLinuxEngine` không khả dụng/permission denied).
- `uv run pytest`: NOT TESTED — pytest thu thập 906 tests, dừng vì DB không khả dụng; không có kết quả test.
- `npm test -- --run src/components/job-detail.test.tsx`, `npm run lint`, `npm run typecheck`: NOT TESTED — các tiến trình không trả kết quả trong môi trường process sandbox; đã dừng.
- `git diff --check`: VERIFIED — sạch; `python -m compileall -q app tests/api/test_export.py` cũng pass.
- `git add`/`git commit`: NOT COMPLETED — Git không tạo được `.git/index.lock` do permission denied; thay đổi còn trong working tree trên task branch.

NOT TESTED: runtime DB/browser, test suite đầy đủ và review/CI độc lập. Không có thay đổi ngoài phạm vi T17.
