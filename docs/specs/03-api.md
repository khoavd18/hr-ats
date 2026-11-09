# 03 · API

Base `/api/v1`. JSON, xác thực bằng cookie HttpOnly chứa JWT (access 30 phút, refresh 7 ngày). Mọi endpoint yêu cầu đăng nhập, trừ health, login và bước lấy CSRF trước đăng nhập; refresh/logout xác thực bằng refresh cookie. Quyền theo `07-security-privacy.md`. OpenAPI tự sinh tại `/docs` (chỉ bật khi `APP_ENV != prod`).

## Hệ thống
- `GET /health` → HTTP 200 `{"status":"ok","db":"ok","redis":"ok"}` khi truy vấn DB và Redis ping đều thành công. Nếu một trong hai không khả dụng: HTTP 503 `{"error":{"code":"SERVICE_UNAVAILABLE","message":"Dịch vụ tạm thời không khả dụng."}}`; không trả lỗi kết nối nội bộ.
- `GET /config/public` → nhãn đơn vị tuyển, danh sách stage và nhãn tiếng Việt. Trong T02 chưa có stage: chỉ trả `{"hiring_unit_label":"Đơn vị tuyển"}` theo `HIRING_UNIT_LABEL`; chưa trả thông tin nghiệp vụ hoặc secret. Xác thực được triển khai tại T04 theo quy tắc chung ở đầu spec.

### Chuẩn lỗi nền (T02)

Các lỗi dùng `{"error":{"code":"...","message":"<tiếng Việt>"}}`: `AppError` giữ code/message/status do service định nghĩa; validation dùng `VALIDATION_ERROR` (422); không tìm thấy dùng `NOT_FOUND` (404); sai method dùng `METHOD_NOT_ALLOWED` (405); lỗi ngoài dự kiến dùng `INTERNAL_ERROR` (500). Không phản chiếu input validation, exception detail hoặc stack trace. Preflight CORS bị từ chối dùng `CORS_REJECTED` (400); origin được cho phép vẫn chỉ là `FRONTEND_ORIGIN`.

## Auth & user
- `POST /auth/login` {email, password} · `POST /auth/logout` · `POST /auth/refresh` · `GET /auth/me`
- `POST /auth/change-password`
- `GET/POST /users`, `PATCH /users/{id}` (admin): tạo, đổi vai trò, khoá

### Contract chi tiết T04

- `GET /auth/csrf` → 204, cấp/giữ cookie đọc được `csrf_token` trước đăng nhập. Mọi POST/PATCH/PUT/DELETE, kể cả login, cần header `X-CSRF-Token` trùng cookie có chữ ký hợp lệ. Có header `Origin` thì phải đúng `FRONTEND_ORIGIN`.
- Login nhận `{email, password}`, chuẩn hoá email trim/lowercase; thành công 200 trả user public và cấp `access_token`, `refresh_token`, `csrf_token`. Refresh cũng trả user và xoay cả ba cookie; token cũ bị thu hồi. Me trả user public. Cookie host-only, `Path=/`, `SameSite=Lax`, `Secure` khi prod; access/refresh có `HttpOnly`. Phản hồi xác thực dùng `Cache-Control: no-store`.
- User public: `{id, email, full_name, role, is_active, last_login_at, created_at, updated_at}`. Không trả `password_hash`, số lần sai, thời điểm khoá tạm hoặc phiên bản xác thực.
- Đăng nhập sai/tài khoản không tồn tại/bị vô hiệu hoá → 401 `INVALID_CREDENTIALS` cùng thông báo; lần sai thứ 5 và trong 15 phút khoá → 423 `ACCOUNT_LOCKED`. Đăng nhập đúng sau thời gian khoá hoặc trước lần sai thứ 5 đặt bộ đếm về 0. Lỗi JWT/phiên bị thu hồi → 401 `UNAUTHORIZED`; thiếu/sai CSRF → 403 `CSRF_INVALID`.
- `POST /auth/change-password` nhận `{current_password, new_password}`. Sai mật khẩu hiện tại → 400 `INVALID_CREDENTIALS`; thành công → 204, thu hồi phiên và xoá cookie. Logout → 204, thu hồi phiên và xoá cookie; vẫn dùng được khi access đã hết hạn.
- `GET /users?page=1&page_size=20` (tối đa 100) → 200 `{items: [user], total}` theo created_at/id, gồm cả tài khoản bị khoá. `POST /users` nhận `{email, full_name, role, password}` → 201 user; trùng email → 409 `EMAIL_EXISTS`.
- `PATCH /users/{id}` nhận các trường `role`, `is_active` → 200 user; không nhận null/trường khác. Không có xoá user. Không cho admin tự bỏ quyền admin hoặc tự khoá → 409 `SELF_LOCKOUT`. Không tìm thấy → 404. Lead/recruiter quản lý user → 403 `FORBIDDEN`.
- Mật khẩu mới/tạo mới: 12–128 ký tự, tên 1–200 ký tự sau trim, email tối đa 254 ký tự. Input không đúng schema → 422 `VALIDATION_ERROR` không phản chiếu dữ liệu đầu vào.

Các mặc định kỹ thuật trên được ghi ở câu hỏi #18–#20; không bổ sung membership Job trước T05.

## Đơn vị tuyển
- `GET/POST /hiring-units`, `PATCH /hiring-units/{id}` (admin, lead)

## Job
- `GET /jobs?status=&owner_id=&q=` · `POST /jobs` · `GET /jobs/{id}` · `PATCH /jobs/{id}`
- `PUT /jobs/{id}/members` {user_ids}
- `GET /jobs/{id}/applications?stage=&ai_level=&q=&sort=ai_score|created_at` → bảng xếp hạng
- `GET /jobs/{id}/pipeline` → ứng viên nhóm theo stage (cho kanban)
- `POST /jobs/{id}/rescore` → chấm lại toàn bộ (khi đổi yêu cầu)
- `GET /jobs/{id}/suggestions?limit=50` → ứng viên trong kho CV gần với Job (vector), chưa có application
- `GET /jobs/{id}/export.xlsx` → xuất bảng xếp hạng (ghi audit)

### Contract xuất Job T17

- `GET /jobs/{id}/export.xlsx` cần đăng nhập và kiểm `jobs.view` từ DB, bao gồm
  quyền owner/member recruiter; Job thiếu → 404, ngoài quyền → 403. Trả workbook
  `.xlsx` không phân trang gồm các Application/Candidate còn hiệu lực theo cùng
  thứ tự mặc định của bảng xếp hạng T14; không áp dụng bộ lọc đang chọn trên UI.
- Cột theo thứ tự: họ tên, email, SĐT, mức AI tiếng Việt, điểm, lý do AI gộp,
  kỹ năng, năm kinh nghiệm, stage tiếng Việt, ngày nhận. Chuỗi do người dùng cung
  cấp được ghi dạng text để Excel không diễn giải thành công thức. Phản hồi có
  `Cache-Control: no-store`, tên `ung-vien-<slug-job>-<ngày>.xlsx`.
- Chỉ sau khi workbook được tạo thành công, ghi audit `action=candidate.export`,
  `entity=job`, `entity_id=job.id`, IP kết nối đã kiểm định; `details` chỉ gồm
  `record_count` và `job_id`. Không ghi bộ lọc hay dữ liệu ứng viên vào audit.

### Contract Đơn vị tuyển và Job T13

- Mọi endpoint cần đăng nhập; POST/PATCH/PUT kiểm CSRF và Origin như T04.
  Phản hồi thành công có `Cache-Control: no-store`. Không có DELETE cho đơn vị
  hoặc Job: ngừng hoạt động bằng `is_active=false`, kết thúc tuyển bằng `closed`.
- `GET /hiring-units?page=1&page_size=20` (tối đa 100), admin/lead →
  `{items: [HiringUnitRead], total}`, gồm cả ngừng hoạt động, thứ tự created_at/id.
  POST → 201, PATCH → 200; input gồm name, kind, contact_name/contact_email/notes
  nullable và is_active. Tên trim 1–200 ký tự, email hợp lệ tối đa 254, notes tối
  đa 10000. PATCH không nhận null cho name/kind/is_active. Không tồn tại → 404.
  Recruiter gọi các endpoint quản lý đơn vị → 403.
- `GET /jobs/options` dành cho cả ba vai trò → `{hiring_units: [{id,name}],
  users: [{id,name}]}`: chỉ đơn vị/người dùng đang hoạt động, thứ tự name/id.
  Không trả email, liên hệ hay quyền quản trị; đây là danh sách chọn cho form,
  không mở quyền GET `/users` hay `/hiring-units` cho recruiter.
- `GET /jobs?page=1&page_size=20&status=&owner_id=&q=` → `{items: [JobResponse],
  total}`, page_size tối đa 100; thứ tự created_at giảm dần rồi id. Recruiter
  chỉ lấy Job là owner/member ngay trong truy vấn, kể cả total/bộ lọc. Admin/lead
  lấy toàn bộ. q tối đa 200 ký tự, trim, tìm chuỗi trong title không phân biệt
  hoa thường; `%`/`_` là ký tự thường, chưa bỏ dấu. Bỏ tham số lọc nếu không chọn.
- POST `/jobs` → 201; GET/PATCH `/jobs/{id}` → 200 `JobResponse`: các trường
  JobRead, thêm hiring_unit_name, owner_name, member_ids và needs_rescore. Không
  trả vector. Không tồn tại → 404, Job ngoài quyền → 403. Mọi user đang hoạt động
  được tạo Job; recruiter tạo với owner là chính mình, sửa Job họ là owner/member
  và quản lý thành viên; chỉ admin/lead được gán/chuyển owner sang người khác.
  Quyền lấy từ DB, không lấy từ owner_id/member_ids đang gửi lên.
- Input tạo có hiring_unit_id, title, owner_id bắt buộc; description mặc định
  chuỗi rỗng, must_have/nice_to_have/member_ids mặc định [], headcount=1,
  status=draft. Các trường location/employment_type/salary_min/salary_max/deadline
  tuỳ chọn và nullable. PATCH chỉ thay trường được gửi; không nhận null cho
  trường bắt buộc/mảng/status. Field thừa (kể cả embedding/opened_at/closed_at)
  bị từ chối. Tiêu đề trim 1–200 ký tự, mô tả tối đa 50000, địa điểm 200,
  hình thức 100; mỗi danh sách yêu cầu tối đa 100 dòng, mỗi dòng trim 1–500 ký tự.
  Lương nguyên 0–2147483647, min ≤ max khi đủ hai đầu; headcount nguyên dương
  tối đa 2147483647. Job `open` cần ít nhất một must_have. PATCH validate bản ghi
  sau khi ghép dữ liệu cũ; input sai → 422 `VALIDATION_ERROR`.
- FK mới chỉ chọn đơn vị/user đang hoạt động; không hợp lệ → 422
  `INVALID_HIRING_UNIT` / `INVALID_JOB_USER`. Giữ tham chiếu cũ đã ngừng hoạt động
  khi sửa thông tin khác. Member tối đa 100 ID, trùng ID được gộp; POST/PATCH hỗ trợ
  member_ids để lưu form nguyên tử. PUT `/jobs/{id}/members` nhận `{user_ids}`
  thay toàn bộ thành viên và trả JobResponse. [] thu hồi toàn bộ membership;
  owner vẫn có quyền. Thành viên tự rời Job nhận thành công rồi mất quyền lần sau.
- Mỗi lần chuyển sang `open` đặt opened_at hiện tại và xoá closed_at; sang
  `closed` đặt closed_at. Gửi lại cùng trạng thái giữ mốc; draft/on_hold giữ mốc cũ.
  Tạo/sửa gọi `embed_job` T11 trước commit; Job/vector/members cùng transaction,
  lỗi tạo vector rollback và trả 503 `EMBEDDING_UNAVAILABLE`, không lỗi provider thô.
- Sửa must_have/nice_to_have khác giá trị trước và có Application chưa xoá →
  `needs_rescore=true`, còn lại false. Không tự chấm lại hoặc đổi stage. UI hỏi
  người dùng, chỉ khi xác nhận mới POST `/jobs/{id}/rescore` theo contract T12.
  Cột số ứng viên theo mức AI và chi tiết bảng xếp hạng thuộc T14.

ASSUMED: chi tiết chưa chốt được ghi ở câu hỏi #52–#54; không đổi schema DB/KPI.

### Contract bảng xếp hạng T14

- `GET /jobs/{id}/applications?page=1&page_size=20&stage=&ai_level=&q=&sort=ai_score`
  cần đăng nhập, kiểm owner/member Job từ DB (admin/lead toàn bộ), kể cả danh sách
  rỗng. Job thiếu → 404, ngoài quyền → 403, input sai → 422. `Cache-Control: no-store`.
- Trả `{items, total, ai_counts}`. Mỗi item chỉ có `id`, `candidate_id`,
  `candidate_name`, `skills`, `years_experience` (decimal dạng chuỗi hoặc null),
  `stage`, `created_at`, `ai_status`, `ai_level`. Không trả liên hệ, text CV,
  vector, điểm số, tiêu chí hay metadata provider trên bảng tóm tắt.
- Chỉ lấy Application chưa xoá và Candidate chưa xoá/gộp/hết hạn (ngày theo TZ).
  `stage`/`ai_level` theo enum; lọc mức AI chỉ lấy `ai_status=done`. q trim tối đa
  200 ký tự, substring không phân biệt hoa thường trong tên/chức danh/kỹ năng;
  `%`/`_` là ký tự thường, chưa bỏ dấu. `total` tính sau lọc, trước phân trang.
- Sắp mặc định: các hồ sơ AI done theo high → medium → low → insufficient, rồi
  hồ sơ chưa đánh giá/đánh giá lỗi; trong mỗi nhóm `ai_score DESC NULLS LAST`,
  `created_at DESC`, `id ASC`. `sort=created_at` chỉ dùng hai khoá cuối.
  page ≥1, page_size 1–100; sort khác bị từ chối. Phân trang offset có thể dịch
  khi worker hoàn thành, thứ tự ổn định khi dữ liệu không đổi.
- `ai_counts` luôn đủ bảy khoá `high, medium, low, insufficient, pending, running,
  failed`, giá trị nguyên không âm, tính toàn Job trước bộ lọc/phân trang. Chỉ
  done tính theo mức (done thiếu mức tính insufficient), trạng thái khác tính
  theo ai_status. GET `/jobs` và mọi JobResponse bổ sung cùng `ai_counts`;
  danh sách Job dùng một truy vấn nhóm cho cả trang theo scope T13.
- GET `/cv-files/{id}` giữ metadata/quyền/audit T07, bổ sung `processing_error`
  (null hoặc `{code: CV_PROCESSING_FAILED, message: <câu Việt cố định>}`),
  `application_id`, `ai_status`. Hai trường Application chỉ có khi file gắn Job,
  ứng viên còn hợp lệ và caller cũng có quyền Job gốc; quyền file thông qua Job
  khác không tiết lộ Application của Job gốc. Không trả cột error thô từ DB.
- Upload trùng SHA giữ contract T07, không tự gắn sang Job khác. UI thông báo
  file đã có trong kho/chưa thêm vào vị trí này; không polling vô hạn hoặc báo
  đã thêm thành công. Các thao tác thêm từ kho thuộc T16.
- Log HTTP thành công cho GET health, trạng thái file và bảng xếp hạng ở DEBUG;
  lỗi vẫn INFO. Khớp route template có hoặc không có tiền tố `/api/v1`, không
  ghi tên file, raw path/query hoặc nội dung CV.

ASSUMED: mặc định T14 ở câu hỏi #55–#57; không đổi schema DB hoặc công thức AI.

## CV & ứng viên
- `POST /cv-files` multipart, nhiều file (PDF, DOCX, JPG, PNG; tối đa 10 MB/file, 50 file/lần), tuỳ chọn `job_id` → trả kết quả từng file theo contract T07 dưới đây
- `GET /cv-files/{id}` (trạng thái xử lý) · `GET /cv-files/{id}/download` (ghi audit)
- `GET /candidates?q=&skills=&min_years=&location=&source=` → tìm kiếm kho CV (full-text) · `GET /candidates/search/semantic?q=` → tìm theo nghĩa
- `GET /candidates/{id}` (ghi audit) · `PATCH /candidates/{id}` (sửa thông tin parse sai)
- `POST /candidates/{id}/merge` {into_id} → gộp trùng
- `POST /candidates/{id}/consent` {consent_at, note}
- `DELETE /candidates/{id}` → soft delete

### Contract kho CV T16

- GET `/candidates` và `/candidates/search/semantic` cần đăng nhập, quyền
  `cv_bank.search` cho cả ba vai trò, trả `{items, total}`, `Cache-Control: no-store`.
  Item chỉ có id/full_name/current_title/years_experience/skills/location/source/
  created_at và `possible_duplicate` (null hoặc cùng thông tin tóm tắt, không lồng
  thêm gợi ý). Không trả liên hệ, consent, CV gốc, vector, parsed_json hoặc Job
  membership. Kho chung không mở thêm quyền đọc file/chi tiết T07/T15.
- Cả hai GET nhận q (tối đa 200 ký tự), skills (tối đa 1000, phân tách dấu phẩy,
  yêu cầu đủ tất cả kỹ năng khớp chính xác), min_years (0–9999.99), location
  (tối đa 200, substring literal), source (enum), page ≥1, page_size 1–100
  (mặc định 20). Bộ lọc kỹ năng/địa điểm không phân biệt hoa/thường/dấu; unknown
  years không đạt min_years. Field query thừa/sai bị từ chối 422. Luôn bỏ ứng viên
  xoá/gộp/hết hạn (ngày theo TZ, retention_until bằng hôm nay vẫn hợp lệ).
- Full-text: q trim, `plainto_tsquery('simple', unaccent(q))` đối chiếu search_tsv
  hiện có, xếp rank giảm dần rồi created_at giảm dần/id tăng dần. q rỗng liệt kê
  theo ngày/id. Không diễn giải q thành cú pháp SQL hoặc tsquery do người dùng viết.
- Semantic cần q không rỗng; tạo vector câu tìm kiếm qua adapter T11, xếp cosine
  tăng dần/id, áp dụng cùng filter và pagination. Không đọc CV gốc. Che liên hệ
  và metadata cá nhân có nhãn trong câu tìm kiếm trước adapter; tên cụ thể dùng
  full-text. Lỗi adapter → 503 `EMBEDDING_FAILED` an toàn, không fallback; fake
  chỉ chứng minh luồng chức năng. total tính trước phân trang.
- Gợi ý `GET /jobs/{id}/suggestions?limit=50` nhận limit 1–50, kiểm quyền Job từ
  DB trước kể cả danh sách rỗng; ngoài quyền → 403, Job thiếu → 404. Trả cùng
  envelope tóm tắt, total là số gợi ý trả về (không phải tổng kho). Chỉ lấy vector
  không null, ứng viên hợp lệ và chưa có Application chưa xoá trong Job, xếp
  cosine với jobs.embedding tăng dần/id. Job thiếu vector → danh sách rỗng.
  Application đã soft delete không ngăn ứng viên xuất hiện lại trong gợi ý.
- Nhãn nghi trùng đọc metadata `possible_duplicate_of` từ file T10 theo lô,
  hai bên đều phải còn hợp lệ. Hiển thị đối xứng để HR so sánh hai bản;
  hint sai UUID/tự trỏ hoặc bên kia đã xoá/gộp/hết hạn bị bỏ qua.
- POST `/candidates/{id}/merge` nhận đúng `{into_id: UUID}`; chỉ admin/lead,
  recruiter → 403. CSRF/Origin như T04; tự gộp → 422 `INVALID_MERGE`, một trong
  hai ứng viên thiếu/xoá/gộp/hết hạn → 404. Thành công 200 tóm tắt đích, no-store.
  Đây là thao tác HR xác nhận, không dựa vào AI để tự gộp.
- Gộp khoá identity T10 rồi Candidate theo id và Application theo id. Một
  transaction chuyển mọi cv_files/applications/activities sang đích, đánh dấu
  nguồn merged_into_id + deleted_at. Nếu cùng Job có hai Application đang hoạt
  động, giữ bản đích, soft delete bản nguồn trước khi đổi candidate_id để giữ
  partial unique index. Bản lưu trữ vẫn giữ id, StageEvent và AiFeedback gốc,
  không mất lịch sử hay ép ghi đè phản hồi; chưa có UI xem lịch sử đã lưu trữ.
  Activity note metadata `{action: candidate_merged, source_id, target_id}` cùng
  transaction, không sao chép nội dung CV. Lỗi ghi activity rollback toàn lượt.
  Giữ thông tin/consent/retention/vector của đích, stage/owner/AI của hồ sơ được
  giữ; không tự gia hạn, chấm lại hoặc gửi email. Không có DELETE dữ liệu thật.
- T12 `ensure_application` bổ sung khoá Candidate và kiểm lại eligibility sau
  khi chờ, trước insert: request đã đọc nguồn trước lúc gộp không thể tạo lại
  Application cho nguồn sau merge. UI chọn nhiều gọi POST `/applications` T12
  riêng từng ứng viên; có lỗi một người vẫn tiếp tục người khác, retry riêng
  người lỗi; 409 APPLICATION_EXISTS được thông báo đã có, không chấm lại ngầm.

ASSUMED: các mặc định quyền gộp/xung đột/lọc ở câu hỏi #62–#64. Không đổi schema,
stack, công thức AI hoặc phạm vi task sau.

### Contract upload và truy cập file T07

- `POST /cv-files`: tên field lặp `files`, tối đa một field chuỗi UUID `job_id`; cần đăng nhập và CSRF. Batch hợp lệ trả **200** `{items: [{index, cv_file, duplicate, error}]}` theo thứ tự đầu vào, `index` bắt đầu từ 0. Thành công có `cv_file` theo schema `CvFileRead`, `error=null`; file lỗi có `cv_file=null`, `error={code,message}` tiếng Việt và `duplicate=false`. Lỗi một file không huỷ các file hợp lệ khác. Batch rỗng/sai field/sai UUID/quá 50 file → 422; Job không tồn tại → 404, không có quyền → 403 trước khi lưu file nào.
- Giới hạn 10 MB = 10 × 1024 × 1024 byte, tính trên nội dung. Nhận diện MIME từ magic bytes, không tin tên đuôi/Content-Type do client cung cấp. DOCX phải là ZIP có content type Word chuẩn và `word/document.xml`; từ chối `.docm`, VBA và content type macro, ZIP mã hoá, đường dẫn bất thường, quá 2000 entry hoặc tổng giải nén quá 50 MiB. Không giải nén ra đĩa. Mã lỗi file: `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `MACRO_NOT_ALLOWED`; thông báo không chứa tên hay nội dung file lỗi.
- File mới tạo `cv_files(pending)`, `uploaded_by` lấy từ phiên, `job_id` đã kiểm quyền. Ghi một activity `cv_uploaded` có payload chỉ `{cv_file_id}`. Commit DB trước khi gửi task `process_cv_file` vào queue `ai`. Phản hồi file mới là snapshot `pending` dù eager/worker có thể hoàn tất ngay; GET trạng thái trả giá trị hiện tại. T10 thay worker tạm T07: extract → che liên hệ → parse → tạo/cập nhật Candidate, gắn candidate_id rồi done; lỗi riêng từng file chuyển failed. T12 nối hook tạo Application khi có job_id và publish chấm sau commit. Chi tiết transaction/metadata tại spec 04.
- SHA-256 trùng trả cùng bản ghi với `duplicate=true` và trạng thái hiện tại; không ghi thêm file/activity/task, không đổi Job hoặc uploader của bản ghi cũ. Kiểm quyền cả bản ghi cũ; không có quyền → lỗi từng file `FORBIDDEN` không lộ metadata/ID. Bản ghi/file ứng viên đã soft delete → `NOT_FOUND`, không phục hồi ngầm. Tạo application cho Job khác thuộc T12/các API nghiệp vụ sau.
- Publish hàng đợi lỗi: giữ file/record đã commit, đặt `status=failed`, lưu lỗi tiếng Việt cố định trong DB (không xuất exception). Upload lại cùng file được phép xếp hàng lại đúng lỗi publish này, giữ nguyên ID và activity. Lỗi storage khi upload → lỗi từng file `STORAGE_UNAVAILABLE`; lỗi storage khi download → HTTP 503 cùng code. DB lỗi sau khi lưu object thì rollback và xoá object vừa tạo.
- `GET /cv-files/{id}` → 200 `CvFileRead`, ghi audit `action=view`, `entity=cv_file`. `GET /cv-files/{id}/download` → byte gốc, MIME đã xác minh, `Content-Disposition: attachment` với tên `cv-{id}.{đuôi}`, `X-Content-Type-Options: nosniff`; ghi audit `action=download` sau khi đọc storage thành công, trước khi trả byte. Cả hai dùng `Cache-Control: no-store`. Audit chỉ có định danh actor/file, thời điểm, IP kết nối nếu hợp lệ; không tin `X-Forwarded-For`.
- Admin/lead đọc mọi file chưa xoá; recruiter cần quyền owner/member ở Job upload hoặc ít nhất một application chưa xoá của ứng viên trong Job được phép. ASSUMED T10 (#45): file không gắn Job cho phép uploader đọc đúng file đã tải kể cả sau khi parse gắn Candidate; quyền này không mở các file khác của cùng Candidate. Thu hồi membership có hiệu lực ngay lần truy cập tiếp theo, uploader không vượt quyền Job. Không tồn tại/đã xoá → 404; tồn tại nhưng không có quyền → 403. Không xuất `storage_key`, raw text, parsed JSON hoặc lỗi provider.

ASSUMED: các chi tiết chưa chốt trước T07 được ghi tại câu hỏi #30–#33. Không đổi schema DB/KPI.

## Hồ sơ ứng tuyển & pipeline
- `POST /applications` {candidate_id, job_id} → thêm ứng viên trong kho vào Job (tự xếp hàng chấm AI)
- `GET /applications/{id}` → chi tiết + kết quả AI + lịch sử stage + email + interview
- `POST /applications/{id}/move` {to_stage, note, rejected_reason?} → trả `{application, suggested_email?}`; nếu stage có mẫu email, trả bản nháp để UI hiện xem trước (không tự gửi)
- `POST /applications/{id}/undo` → hoàn tác lần đổi stage gần nhất (trong 24 giờ, đúng người đã đổi hoặc lead/admin)
- `POST /applications/{id}/ai-feedback` {verdict, corrected_level?, comment?}
- `POST /applications/{id}/rescore`
- `POST /applications/{id}/notes` {text} → activity `note`

### Contract thêm hồ sơ và chấm lại T12

- Cả ba POST cần đăng nhập và CSRF. Admin/lead có quyền toàn bộ; recruiter cần
  owner/member Job ở DB tại thời điểm gọi. `applications.owner_id` riêng không
  cấp quyền Job. Không cho caller truyền owner, stage hoặc ai_*; field thừa/sai
  UUID → 422 theo envelope chung.
- `POST /applications` nhận đúng `{candidate_id, job_id}` → **201** ApplicationRead,
  `Cache-Control: no-store`. Stage=new, owner=owner Job, ai_status=pending; trả
  snapshot trước publish kể cả eager worker đã hoàn tất. Job/ứng viên không
  tồn tại, ứng viên đã xoá/gộp/hết hạn → 404; không có quyền Job → 403; cặp
  candidate/job có Application chưa xoá → 409 `APPLICATION_EXISTS`. Không phục hồi
  Application đã xoá, được phép tạo mới theo partial unique index. Thêm từ kho
  chỉ dùng quyền kho tóm tắt và quyền Job, không đọc/trả CV gốc.
- `POST /applications/{id}/rescore` → **202** ApplicationRead snapshot pending,
  no-store. Application đã xoá/ứng viên không hợp lệ → 404; quyền theo Job. Xoá
  kết quả AI cũ khi đặt pending, giữ stage/owner; commit trước publish.
- `POST /jobs/{id}/rescore` → **202** `{"status":"pending"}`: nhận yêu cầu bulk,
  không đồng nghĩa mọi hồ sơ đã chấm xong. Job không tồn tại → 404, không quyền →
  403. Worker chấm từng Application chưa xoá với ứng viên còn hợp lệ.
- Publish score lỗi giữ Application đã tạo, đặt ai_status=failed và trả **201**
  snapshot failed ở create; rescore một hồ sơ trả **503** `AI_QUEUE_UNAVAILABLE`
  và giữ failed để thử lại. Publish bulk task lỗi trả cùng 503, chưa reset điểm cũ.
  Lỗi provider trong worker không thành lỗi HTTP của yêu cầu đã nhận: lưu failed,
  không trả exception gốc. Retry bằng endpoint rescore. Chi tiết idempotency và
  khoảng trống commit/publish tại spec 04/câu hỏi #49–#51.

### Contract hồ sơ và phản hồi T15

- `GET /applications/{id}` → 200 `{application: ApplicationRead, candidate:
  CandidateRead, cv_files, feedback, activities, loaded_at}`. Kiểm Job owner/member
  từ DB; admin/lead toàn bộ. Application thiếu/đã xoá hoặc ứng viên đã xoá/gộp/hết
  hạn → 404; ngoài quyền Job → 403, kể cả khi là owner Application. Thành công
  ghi audit `action=view, entity=candidate, entity_id=candidate.id` (`candidate.view`),
  IP kết nối đã kiểm định; không tin X-Forwarded-For. Commit audit trước trả nội dung.
- `cv_files` chỉ file chưa xoá của ứng viên, kiểm quyền file theo T07, thứ tự mới
  nhất rồi id; mỗi file chỉ `{id, mime_type, status, extracted_text}`. Text chỉ có
  với DOCX; PDF/ảnh dùng GET download T07 có audit và attachment. Web nhận byte có
  cookie qua API client, tạo URL blob cho viewer và thu hồi URL khi đóng/đổi file.
  Không trả storage_key, parsed_json, vector hoặc lỗi xử lý thô.
- `feedback` là phản hồi hiện tại của chính caller hoặc null. `activities` chỉ
  Application đang xem, bỏ activity đã xoá, mới nhất trước (occurred_at/id), dùng
  ActivityRead cộng actor_name nullable. Chỉ hiển thị nhãn loại đã dịch và nội dung
  ghi chú do người dùng nhập; không render payload dạng dữ liệu kỹ thuật. Các bảng
  email/interview và thao tác stage được bổ sung theo T19–T23.
- `POST /applications/{id}/ai-feedback` → 200 AiFeedbackRead. Input đúng
  `{verdict: agree|disagree, corrected_level?, comment?}`; disagree cần mức sửa
  thuộc bốn mức AI, agree không nhận mức sửa. comment nullable hoặc trim 1–10000
  ký tự. Upsert nguyên tử theo (application_id, user_id); user lấy từ phiên, gửi
  lần sau thay toàn bộ phản hồi trước (field bỏ qua trở về null). Giữ id/created_at,
  cập nhật updated_at; phản hồi user khác độc lập. Mỗi lần ghi activity ai_feedback
  với payload chỉ verdict/corrected_level; phản hồi và activity cùng transaction,
  lỗi rollback cả hai. Không đổi điểm AI, stage, owner hoặc gửi email.
- `POST /applications/{id}/notes` nhận `{text}` trim 1–10000 ký tự → 201
  ProfileActivity. Lưu activity note với payload `{text}`, actor/Job/ứng viên lấy
  từ phiên/hồ sơ có quyền. Đây là nội dung HR chủ động nhập, lưu trong DB nghiệp
  vụ, không đi qua bộ log metadata `log_activity` và không ghi vào log ứng dụng.
  Không nới kiểm soát payload tự động cho những activity khác.
- `PATCH /candidates/{id}` → 200 CandidateRead; recruiter cần ít nhất một
  Application chưa xoá của ứng viên trong Job có quyền, admin/lead toàn bộ;
  ứng viên thiếu/đã xoá/gộp/hết hạn → 404, ngoài quyền → 403. Cho sửa full_name
  (trim 1–200, không null), email (nullable, chuẩn hoá/validate như T04), phone
  (nullable, trim tối đa 50), location/current_title (nullable, trim 1–200),
  years_experience (nullable, 0–9999.99, tối đa hai số lẻ), skills (tối đa 100
  chuỗi trim 1–200, không null). Chỉ thay trường được gửi; không cho sửa consent,
  retention, nguồn, vector hoặc text CV. Sửa thông tin hiển thị không gọi lại AI;
  text CV/ẩn danh/vector/kết quả chấm giữ theo bản CV đã xử lý.
- Mọi endpoint cần đăng nhập; mutation cần CSRF/Origin T04. Field thừa/input sai
  → 422 envelope không phản chiếu input. Thành công `Cache-Control: no-store`.

ASSUMED: các mặc định T15 ghi tại câu hỏi #59–#61; không đổi schema DB/KPI.

## Phỏng vấn, offer, placement
- `POST /applications/{id}/interviews` · `PATCH /interviews/{id}` · `GET /interviews?from=&to=&mine=true`
- `GET /interviews/{id}/ics` → file lịch .ics để gửi kèm email
- `POST /applications/{id}/offers` · `PATCH /offers/{id}`
- `POST /applications/{id}/placement` · `PATCH /placements/{id}`

## Email
- `GET/POST /email-templates`, `PATCH /email-templates/{id}` (admin, lead) · `POST /email-templates/{id}/preview` {application_id}
- `POST /email-messages` {application_id, template_id?, subject, body, to_email} → tạo `draft`
- `POST /email-messages/{id}/send` → `queued` (đây là bước "xác nhận")
- `POST /email-messages/{id}/cancel` · `GET /email-messages?application_id=`

## Task & hoạt động
- `GET /tasks?mine=true&status=&due_before=` · `POST /tasks` · `PATCH /tasks/{id}`
- `GET /activities?job_id=&application_id=&actor_id=&from=&to=`

## Báo cáo
- `GET /reports/summary?from=&to=&recruiter_id=&job_id=&hiring_unit_id=` → các KPI trong `06`
- `GET /reports/funnel?job_id=&from=&to=` → số lượng và tỉ lệ theo stage
- `GET /reports/recruiters?from=&to=` → bảng theo recruiter
- `GET /reports/ai-agreement?from=&to=` → tỉ lệ đồng ý với AI
- `GET /reports/export.xlsx?...`

## Quản trị dữ liệu
- `GET/POST /data-requests` · `POST /data-requests/{id}/execute` (admin): xoá vĩnh viễn file, text, embedding của ứng viên; giữ bản ghi ẩn danh cho thống kê
- `GET /audit-log?entity=&actor_id=` (admin)
