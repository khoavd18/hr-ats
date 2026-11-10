# 03 · API

## Contract T24 · Trạng thái hộp mail

`GET /api/v1/settings/mailbox`: chỉ admin/lead đang hoạt động; chưa đăng nhập
401, recruiter 403. Trả 200 `{enabled: bool, last_read_at: ISO timestamp|null,
last_error: code|null}`. enabled lấy IMAP_ENABLED; metadata lượt đọc gần nhất
lưu Redis key `hr-ats:imap:status`, không chứa host/user/password/header/body.
Mã lỗi: IMAP_NOT_CONFIGURED, IMAP_READ_FAILED, IMAP_MESSAGE_TOO_LARGE,
IMAP_STATUS_UNAVAILABLE; null khi lần đọc gần nhất không lỗi. Redis mất hoặc
metadata sai vẫn trả enabled và lỗi trạng thái an toàn; chưa từng đọc trả null.
Không có API ghi cấu hình, gọi poll thủ công hay trả danh sách/nội dung thư.
Trang Job hiển thị mã tính từ 8 ký tự hex đầu UUID: `[JOB-XXXXXXXX]`; không
thêm field vào DTO Job hoặc nhận mã Job từ client.

Base `/api/v1`. JSON, xác thực bằng cookie HttpOnly chứa JWT (access 30 phút, refresh 7 ngày). Mọi endpoint yêu cầu đăng nhập, trừ health, login và bước lấy CSRF trước đăng nhập; refresh/logout xác thực bằng refresh cookie. Quyền theo `07-security-privacy.md`. OpenAPI tự sinh tại `/docs` (chỉ bật khi `APP_ENV != prod`).

## Hệ thống
- `GET /health` → HTTP 200 `{"status":"ok","db":"ok","redis":"ok"}` khi truy vấn DB và Redis ping đều thành công. Nếu một trong hai không khả dụng: HTTP 503 `{"error":{"code":"SERVICE_UNAVAILABLE","message":"Dịch vụ tạm thời không khả dụng."}}`; không trả lỗi kết nối nội bộ.
- `GET /config/public` → `{hiring_unit_label, stages: [{code, label}]}`; cần đăng nhập. T19 bổ sung đủ tám stage theo thứ tự ở spec 02, gồm cả cột kết thúc; nhãn `submitted` là `Đã gửi {HIRING_UNIT_LABEL}`. Không trả cấu hình nội bộ hoặc secret.

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
- Chỉ lấy Application chưa xoá và Candidate chưa xoá/gộp/hết hạn (ngày theo APP_TIMEZONE).
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
  xoá/gộp/hết hạn (ngày theo APP_TIMEZONE, retention_until bằng hôm nay vẫn hợp lệ).
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
  T29: nếu nguồn hoặc đích có yêu cầu delete đang open → 409 DATA_REQUEST_OPEN;
  giữ nguyên identity, hồ sơ và yêu cầu để admin xác nhận xoá đúng ứng viên.
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

### Contract pipeline T19

- Ba endpoint move/undo/pipeline cần đăng nhập; POST kiểm CSRF/Origin theo T04.
  Admin/lead có quyền toàn bộ, recruiter phải là owner/member Job ở DB;
  `applications.owner_id` riêng không cấp quyền. Ngoài quyền → 403. Hồ sơ thiếu/
  đã xoá, ứng viên đã xoá/gộp/hết hạn → 404; Job thiếu → 404. Phản hồi thành công
  có `Cache-Control: no-store`. Không gọi AI, xếp hàng hoặc gửi email.
- POST `/applications/{id}/move` nhận đúng `{to_stage, note?, rejected_reason?}`.
  `to_stage` theo enum, note nullable hoặc trim 1–10000 ký tự. `rejected_reason`
  chỉ nhận sáu chuỗi chuẩn: `thiếu kỹ năng`, `thiếu kinh nghiệm`, `lương không phù hợp`,
  `ứng viên không phản hồi`, `đơn vị tuyển từ chối`, `khác`; bắt buộc khi đích
  `rejected`, phải bỏ qua/null ở đích khác. Field thừa/input sai → 422
  `VALIDATION_ERROR`, không phản chiếu input. Thành công 200
  `{application: ApplicationRead, suggested_email, email_notice}`; nháp T23 bên dưới.
- Các cặp hợp lệ theo spec 02: bước kế tiếp/lùi một bước trên chuỗi
  new → screening → submitted → interview → offer → hired; từ năm bước mở
  new…offer còn được sang rejected/withdrawn. Cùng bước, nhảy bước hoặc move từ
  hired/rejected/withdrawn → 409 `INVALID_STAGE_TRANSITION`; stage kết thúc chỉ
  khôi phục qua undo. T19 chưa tạo interview/offer/placement (T21 sở hữu).
- Move khoá hàng Application, đọc lại trạng thái và kiểm quyền/ứng viên sau khi
  chờ. Một transaction cập nhật stage/stage_entered_at/rejected_reason, thêm
  StageEvent và activity `stage_changed`. Event lưu from/to/actor/note/occurred_at;
  activity chỉ metadata from_stage/to_stage/stage_event_id/undo_of (null với move).
  Note chủ động HR nhập chỉ lưu DB nghiệp vụ ở event, không sao chép sang payload
  hoặc log ứng dụng. Giữ owner và toàn bộ kết quả AI. Lỗi ghi event/activity
  rollback cả stage, mốc thời gian và lý do.
- POST `/applications/{id}/undo` không cần body → 200 ApplicationRead. Chỉ undo
  event mới nhất chưa xoá, có from_stage hợp lệ và to_stage khớp trạng thái hiện
  tại. Event khởi tạo from_stage=null, lịch sử thiếu/không khớp hoặc đã undo →
  409 `UNDO_NOT_AVAILABLE`. Recruiter khác actor của event → 403 `UNDO_FORBIDDEN`,
  kể cả có quyền cùng Job. Lead/admin vẫn phải tuân thủ giới hạn thời gian.
- Cho undo khi 0 ≤ hiện tại − occurred_at ≤ 24 giờ (đúng 24 giờ vẫn được);
  quá hạn hoặc mốc tương lai → 409 `UNDO_EXPIRED`. Ghi event đảo chiều mới và
  activity mới với undo_of trỏ event gốc; không sửa/xoá lịch sử. Stage trở về
  bước mở trước đó, rejected_reason=null, stage_entered_at là lúc undo. Một
  lần đổi chỉ undo một lần, không undo tiếp event hoàn tác; move mới mở lượt
  undo mới. Khoá cùng hàng đảm bảo hai move/undo trùng đồng thời chỉ ghi một lượt.
- GET `/jobs/{id}/pipeline` → 200 `{columns: [{stage, items, total}], total}`,
  đủ tám cột theo thứ tự enum kể cả rỗng. Item chỉ gồm id/candidate_id/
  candidate_name/stage/stage_entered_at/owner_id/ai_status/ai_level; không có
  liên hệ, CV, ghi chú, vector hoặc thông tin provider. Chưa phân trang/filter;
  xếp trong cột theo stage_entered_at tăng dần rồi id. Cùng eligibility với
  bảng xếp hạng T14; kiểm quyền Job trước kể cả không có hồ sơ.

ASSUMED: các mặc định undo/shape/lý do tại câu hỏi #68–#70; không đổi schema.

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

### Contract T21

- Tất cả endpoint kiểm đăng nhập và scope Job từ DB như T19; mutation kiểm
  CSRF/Origin. Không quyền → 403, bản ghi/Application/ứng viên thiếu hoặc đã
  ẩn/gộp/hết hạn → 404. Response thành công no-store. Không có DELETE, không
  gọi AI, queue hay gửi email. Field thừa/input sai → 422 envelope an toàn.
- POST trả 201 bản ghi; PATCH trả 200 cùng DTO gồm id/application_id,
  created_at/updated_at và các trường nghiệp vụ dưới đây; không có deleted_at.
  PATCH chỉ thay field được gửi. Trường bắt buộc không nhận null; optional
  nhận null để xoá giá trị. Không nhận application_id/id hoặc timestamp từ body.
- Interview POST `{round=1, scheduled_at, duration_minutes=60,
  location_or_link?, interviewers=[]}`; round nguyên dương tới 2147483647,
  duration nguyên 1–1440; scheduled_at bắt buộc có offset. interviewers tối đa
  50 chuỗi trim 1–254 ký tự (tên/email); không phân giải tài khoản hoặc gửi thư.
  location nullable hoặc trim 1–10000. PATCH nhận các field trên và
  result=pending|pass|fail|no_show, feedback nullable/trim 1–10000. POST không
  nhận result/feedback, mặc định pending/null. Tạo đầu tiên từ submitted đổi
  stage qua pipeline.move sang interview; tạo thêm ở interview không thêm event.
  Tạo lại sau undo về submitted cũng đưa sang interview. Bước khác → 409
  INVALID_STAGE_TRANSITION. Thay kết quả không tự từ chối hay đổi stage.
- GET `/interviews?from=&to=&mine=true&page=1&page_size=20` → `{items,total}`.
  from/to tuỳ chọn là ngày ISO (nửa đêm giờ Việt Nam) hoặc timestamp có offset;
  khoảng [from,to), start phải nhỏ hơn end. page ≥1, page_size 1–100; xếp theo
  scheduled_at/id. mine=true là Application.owner_id = caller, vẫn lọc scope
  Job kể cả recruiter là owner hồ sơ; mine=false lấy toàn bộ Job có quyền.
  Bỏ các bản đã ẩn và ứng viên hết hạn/gộp; total sau lọc/trước phân trang.
- GET `/interviews/{id}/ics` → attachment text/calendar UTF-8 với UID từ UUID,
  VTIMEZONE và DTSTART/DTEND TZID Asia/Ho_Chi_Minh, thời lượng chính xác;
  DTSTAMP từ updated_at UTC. Dùng icalendar để escape/fold UTF-8. Nội dung chỉ
  vòng/thời điểm/thời lượng/địa điểm, không CV/liên hệ/feedback/attendee hoặc
  hành động gửi thư. Tên tệp interview-{id}.ics, no-store và nosniff.
- Offer POST `{salary?, start_date?, status=draft|sent, notes?}`. Salary nguyên
  0–2147483647; notes nullable/trim 1–10000. PATCH nhận cùng field, status thêm
  accepted/declined; chỉ draft→sent→accepted|declined hoặc giữ nguyên. Đổi
  ngược → 409 INVALID_OFFER_STATUS. Khi ghi nhận sent đặt sent_at ở server và
  chuyển interview→offer qua pipeline; đã offer thì không thêm event. Gửi
  lại status=sent giữ sent_at và không thêm activity. Draft không đổi stage;
  accepted/declined giữ stage. T21 ghi nhận offer đã gửi bằng cách khác, gửi
  email trong hệ thống vẫn phải qua xem trước/xác nhận T23.
- Placement POST `{start_date, fee_amount?, guarantee_until?}`, PATCH nhận
  cùng field cộng status=active|left_in_guarantee|completed. Phí nguyên
  0–2147483647, guarantee_until ≥ start_date, kiểm cả dữ liệu cũ + PATCH.
  Tạo ở offer chuyển hired qua pipeline; đã hired chỉ bổ sung bản ghi. Mỗi
  Application đúng tối đa một placement kể cả bản ẩn: trùng → 409 PLACEMENT_EXISTS.
  Row lock + UNIQUE bảo vệ hai yêu cầu đồng thời. PATCH không đổi stage.
- GET `/applications/{id}` bổ sung interviews (scheduled_at/id tăng), offers
  (created_at giảm/id tăng), placement hoặc null; chỉ bản chưa ẩn. Activity
  interview_scheduled/offer_made chỉ lưu interview_id/offer_id; nhận xét, liên
  hệ người phỏng vấn và ghi chú offer chỉ trong bảng nghiệp vụ có quyền.
  Mọi bản ghi và stage/history/activity cùng transaction, lỗi rollback cả lượt.

ASSUMED: các mặc định T21 tại câu hỏi #74–#77; không thay ma trận stage/KPI.

## Email
- `GET/POST /email-templates`, `PATCH /email-templates/{id}` (admin, lead) · `POST /email-templates/{id}/preview` {application_id}
- `POST /email-messages` {application_id, template_id?, subject, body, to_email} → tạo `draft`
- `POST /email-messages/{id}/send` → `queued` (đây là bước "xác nhận")
- `POST /email-messages/{id}/cancel` · `GET /email-messages?application_id=`

### Contract mẫu email T22

- Tất cả endpoint `/email-templates` chỉ admin/lead, kiểm tại service bằng
  `email_templates.manage`; recruiter kể cả owner Job không được quản lý/xem
  trước ở Cài đặt. Mutation và preview kiểm CSRF/Origin theo T04; response
  thành công có Cache-Control: no-store. Gửi email cho recruiter thuộc T23.
- GET `?page=1&page_size=20` (tối đa 100) trả `{items,total}`, gồm mẫu ngừng dùng,
  thứ tự created_at/id. Item gồm id/key/name/stage/subject/body/is_active/
  requires_confirmation/created_at/updated_at. POST → 201, PATCH `/{id}` → 200.
  Input POST: key, name, subject, body bắt buộc; stage=null, is_active=true,
  requires_confirmation=true mặc định. Key `[a-z][a-z0-9_]{0,63}` bất biến;
  name trim 1–200, subject trim 1–500 và một dòng, body trim 1–20000 ký tự.
  PATCH chỉ sửa trường gửi lên, stage cho null, các trường còn lại không null;
  field thừa bị từ chối. Chỉ cv_received được không yêu cầu xác nhận. Trùng key
  → 409 EMAIL_TEMPLATE_EXISTS; thiếu ID → 404; input sai → 422. Không DELETE;
  ngừng dùng bằng PATCH is_active=false. Nội dung sai cú pháp bị từ chối khi lưu.
- GET `/email-templates/preview-options?page=&page_size=&q=` trả `{items,total}`,
  mỗi item `{id: application_id,candidate_name,job_title}`. Chỉ hồ sơ/ứng viên
  chưa xoá/gộp/hết hạn; q trim tối đa 200, substring tên/vị trí không phân biệt
  hoa thường, wildcard là ký tự thường, xếp candidate_name/application_id.
  Không trả liên hệ hoặc CV. Admin/lead vốn có scope toàn bộ Job.
- POST `/{id}/preview` nhận `{application_id,subject?,body?}`; hai nội dung tuỳ
  chọn cho xem trước bản đang soạn, bỏ/null dùng nội dung đã lưu. Trả
  `{subject,body,body_html}`; body là text sau thay biến, body_html an toàn.
  Kiểm Job và eligibility trước dựng context; mẫu ngừng dùng vẫn xem trước được
  để sửa. Không lưu bản nháp, ghi nội dung vào log, gọi provider hoặc đổi stage.
- Render chỉ nhận 10 biến spec 06; lỗi thiếu/blank → 422
  `EMAIL_MISSING_<TÊN_BIẾN_UPPERCASE>`, thông báo Việt nêu tên biến. Biến ngoài
  danh sách → EMAIL_VARIABLE_UNKNOWN; thuộc tính/call/filter/loop/include/cú pháp
  tính toán, tiêu đề xuống dòng hoặc vượt giới hạn → EMAIL_TEMPLATE_INVALID.
  UI ánh xạ mã lỗi sang nhãn Việt cục bộ, không hiển thị raw server message.

ASSUMED: mặc định T22 tại câu hỏi #78–#81.

### Contract gửi email T23

- Mọi endpoint message cần đăng nhập, scope Job owner/member từ DB (admin/lead
  toàn bộ), hồ sơ/ứng viên còn hiệu lực; mutation kiểm CSRF/Origin. Response
  thành công no-store. Kho CV chung không cấp quyền message. Không có DELETE.
- `/move` giữ transaction T19, thêm `suggested_email` là null hoặc
  `{application_id,template_id,to_email,subject,body,body_html,has_calendar}`,
  chưa ghi EmailMessage hoặc publish. Chọn mẫu đang bật theo stage, created_at/id
  tăng dần. Người nhận là email ứng viên; mẫu stage submitted/key
  submitted_to_unit dùng contact_email của đơn vị. Thiếu email hoặc biến/lịch:
  stage vẫn được lưu, nháp null, `email_notice` là mã EMAIL_NO_ADDRESS,
  EMAIL_UNIT_NO_ADDRESS hoặc mã render T22; không trả dữ liệu nội bộ. Không có
  vấn đề thì email_notice=null. Không gợi ý nếu không có mẫu đang bật.
- GET `/email-messages/templates?application_id=` trả `{items:[{id,name}]}` chỉ
  mẫu đang bật, cho mọi user có quyền hồ sơ; không mở quyền quản lý mẫu T22.
  POST `/email-messages/preview` nhận `{application_id,template_id}`, trả cùng
  nháp như move, thiếu dữ liệu trả 422; không lưu/gửi/đổi stage.
- POST `/email-messages` nhận `{application_id,template_id?,to_email,subject,body}`
  → 201 draft. application_id bắt buộc; template_id nullable, phải đang bật nếu
  chọn. Một địa chỉ thuần tối đa 254 ký tự, subject trim 1–500/một dòng/không
  ký tự điều khiển, body trim 1–100000. Body là văn bản đã render, không đánh giá
  Jinja lần hai; tạo body_html bằng Markdown escape T22. Không nhận status,
  body_html, cc, created_by hoặc message_id từ client. Interview invite cần lịch.
- POST `/{id}/send` là hành động xác nhận duy nhất trong T23 → 202 snapshot
  queued, commit trước publish. Chỉ draft/failed chuyển queued; queued/sent lặp
  trả hiện trạng, không publish lại. Cancelled → 409 EMAIL_INVALID_STATUS.
  Lần xác nhận mới ghi created_by là người xác nhận, message_id RFC mới,
  scheduled_for hiện tại và xoá error. Không sửa nội dung sau lưu nháp; khi lỗi
  xếp hàng UI giữ ID để thử lại cùng nháp. Publish lỗi → failed/không hẹn retry,
  trả 503 EMAIL_QUEUE_UNAVAILABLE an toàn. Không có tự gửi theo stage hoặc
  requires_confirmation=false; cv_received tự động thuộc T24.
- POST `/{id}/cancel` → 200 cancelled, xoá scheduled_for/error; lặp an toàn,
  sent → 409. Khoá hàng chung với worker: huỷ trước SMTP thì không gửi; khi SMTP
  đã được chấp nhận thì không thu hồi thư. Failed có scheduled_for là đang hẹn
  retry; HR được huỷ hoặc bấm Gửi lại để cấp lượt gửi mới.
- GET `/email-messages?application_id=&page=1&page_size=20` (tối đa 100) →
  `{items,total}`, xếp created_at giảm dần/id tăng dần; bỏ message đã soft delete.
  Item: id/application_id/template_id/to_email/subject/body_html/status/sent_at/
  scheduled_for/error/created_at. Error chỉ thông báo Việt cố định; không trả
  lỗi SMTP/credential/protocol. Toàn bộ danh sách kiểm quyền kể cả rỗng.
- Template ngừng dùng → 422 EMAIL_TEMPLATE_INACTIVE; nội dung nháp render vượt
  giới hạn/recipient lỗi → EMAIL_INVALID_DRAFT. Thiếu bản ghi → 404, ngoài scope
  → 403, input sai → 422. Mọi mã lỗi có ánh xạ Việt tại frontend.

ASSUMED: chi tiết T23 tại câu hỏi #82–#85; giữ schema EmailMessage của T22.

## Task & hoạt động
- `GET /tasks?mine=true&status=&due_before=` · `POST /tasks` · `PATCH /tasks/{id}`
- `GET /activities?job_id=&application_id=&actor_id=&from=&to=`

### Contract T25

- GET/POST/PATCH tasks và GET overview cần đăng nhập; mutation kiểm CSRF/Origin
  T04, response thành công no-store. Recruiter chỉ xem/sửa việc được giao cho
  mình, vẫn cần quyền Job hiện tại nếu có liên kết. Admin/lead sửa toàn bộ,
  mine=false xem toàn bộ; recruiter mine=false → 403. Task/hồ sơ đã ẩn hoặc
  ứng viên đã xoá/gộp/hết hạn bị loại khỏi danh sách; mất quyền Job không trả
  task title/description hay metadata liên kết. PATCH task thiếu/ẩn → 404,
  ngoài scope/không còn eligible → 403. Không có DELETE.
- GET `/tasks?page=1&page_size=20&mine=true&status=&due_before=` trả
  `{items,total}`; page≥1, page_size 1–100. Bỏ status lấy todo/doing; truyền
  status lấy đúng enum. due_before là timestamp có offset, lọc due_at < mốc;
  task không hạn không khớp. Xếp due_at tăng (null cuối), id; total trước phân
  trang. Item gồm id/title/description/assignee_id/created_by/job_id/
  application_id/due_at/status/completed_at/created_at/updated_at; không CV,
  liên hệ hay deleted_at.
- POST nhận `{title,description?,assignee_id?,job_id?,application_id?,due_at?}`
  → 201 TaskRead. Title trim 1–200, description nullable/trim 1–10000; due_at
  nullable hoặc timestamp có offset. Assignee bỏ/null là caller; recruiter
  chỉ tự giao, admin/lead chọn user active có quyền Job. Sai user → 422
  INVALID_TASK_ASSIGNEE, ngoài quyền → 403. Application suy ra Job, gửi Job
  khác → 422 INVALID_TASK_LINK; liên kết thiếu/không eligible → 404.
- PATCH chỉ nhận title/description/due_at/status; title/status không null;
  optional null xoá giá trị. Không đổi người giao/nhận/liên kết qua PATCH.
  Khoá hàng, khi chuyển vào done đặt completed_at server và activity task_done
  chỉ payload task_id, cùng transaction; lặp done giữ timestamp/không thêm
  activity. Mở lại todo/doing hoặc cancelled xoá completed_at. Không đổi stage,
  gọi AI hoặc gửi email ứng viên. Field thừa/input sai → 422 envelope an toàn.
- GET `/tasks/application-options?job_id=&q=&page=1` kiểm quyền Job trước kể
  cả danh sách rỗng; trả `{items:[{id,job_id,name}],total}` (id là Application),
  chỉ hồ sơ eligible; q trim≤200, substring literal tên, xếp tên/id, 20/trang.
  Form dùng `/jobs` và `/jobs/options` hiện có để chọn Job/người nhận.
- GET `/overview` trả `{today_tasks:TaskList,interviews,interview_total,jobs,
  job_total,unseen_cv_count}`. Việc của caller mở có due_at trước hết hôm nay
  (kể cả quá hạn); lịch hôm nay/ngày mai [nửa đêm,nửa đêm+2 ngày), xếp giờ/id;
  Job open chưa đủ placement chưa ẩn, deadline từ hôm nay tới hôm nay+7 (inclusive),
  xếp deadline/id. Mỗi danh sách tối đa 20, total đầy đủ. Lịch chỉ id/
  application_id/job_id/candidate_name/job_title/scheduled_at; Job chỉ
  id/title/deadline. Lịch và Job lọc owner/member Job của recruiter, admin/lead
  toàn bộ. CV chưa xem đếm Application eligible stage=new trong scope, chưa
  có audit view candidate của caller sau thời điểm tạo Application. Ngày theo
  Asia/Ho_Chi_Minh; đây là số phục vụ màn Tổng quan, không định nghĩa KPI T26.

ASSUMED: các mặc định T25 tại câu hỏi #90–#93. Endpoint activities tổng hợp
chưa nằm trong T25; lịch sử hồ sơ dùng GET applications/{id} hiện có.

## Báo cáo
- `GET /reports/summary?from=&to=&recruiter_id=&job_id=&hiring_unit_id=` → các KPI trong `06`
- `GET /reports/funnel?job_id=&from=&to=` → số lượng và tỉ lệ theo stage
- `GET /reports/recruiters?from=&to=` → bảng theo recruiter
- `GET /reports/ai-agreement?from=&to=` → tỉ lệ đồng ý với AI
- `GET /reports/export.xlsx?...`

### Contract T26

Năm endpoint cùng query model: `from` và `to` bắt buộc dạng YYYY-MM-DD;
khoảng `[from,to)` theo Asia/Ho_Chi_Minh dài 1–366 ngày. Ngày đầu năm 0001
không nhận vì không biểu diễn được UTC−7 giờ của mốc nửa đêm đó. Optional
`recruiter_id`, `job_id`, `hiring_unit_id` là UUID; bỏ tham số nếu không lọc.
Field thừa/UUID/ngày/khoảng sai → 422 VALIDATION_ERROR (envelope an toàn).
Tất cả cần đăng nhập, no-store, quyền reports.view tại service. Recruiter
không truyền ID thì suy ra chính mình; ID khác → 403; Job ngoài scope → 403
kể cả kết quả rỗng; Job hoặc recruiter tường minh không tồn tại → 404.
Đơn vị không khớp/không có trong scope → kết quả rỗng, không lộ danh mục riêng.
Admin/lead xem team; mọi fact recruiter đọc vẫn trong quyền Job hiện tại.

- `summary` → `{period,metrics,new_cvs_by_day}`. `period` gồm from_date/to_date,
  timezone, as_of (timestamp có offset), definition_status=`draft` và ba ID
  bộ lọc hiệu lực. `new_cvs_by_day:[{date,count}]` đủ từng ngày trong kỳ,
  ngày không có CV là 0, xếp ngày tăng dần.
- `metrics` gồm new_cvs/screened/submitted/offers/placements/overdue_jobs là
  integer; interviews=`{total,elapsed,upcoming}`; time_to_fill=
  `{days:number|null,sample_count,excluded_count}`; stage_duration là map đủ
  tám stage với cùng shape median; placement_revenue=
  `{amount:integer|null,known_count,missing_count}` (VND); ai_agreement=
  `{agree,disagree,total,rate:number|null}`; activities là map đủ ActivityType
  sang số đếm; funnel như endpoint funnel bên dưới.
- `funnel` → `{period,stages:[{stage,count,next_stage,next_count,conversion_rate}]}`.
  Đủ tám stage theo thứ tự enum; next_stage/next_count null ở hired/rejected/
  withdrawn. Rate dạng phần số, ví dụ 0.8 là 80%, không làm tròn/cap. Mẫu số
  bằng 0 → null; flow ratio có thể >1, không phải cohort conversion.
- `recruiters` → `{period,items:[{recruiter_id,recruiter_name,metrics}]}`;
  mỗi item có đủ bộ metrics, xếp tên/ID. Recruiter chỉ một hàng của mình;
  team giữ inactive và admin/lead có dữ liệu, các recruiter chưa có dữ liệu
  có hàng 0/null. Hàng recruiter_id/name=null là chưa gán/hệ thống, xếp cuối.
  Không trả email/quyền/user credential. SQL nhóm toàn roster, không N+1.
- `ai-agreement` → `{period,agreement:{agree,disagree,total,rate}}`; cùng công
  thức/population với summary. Ratio dùng tổng tử/mẫu, không trung bình cá nhân.
- `export.xlsx` → MIME xlsx, attachment `bao-cao-<from>-<to>.xlsx`. Cùng bộ
  lọc/quyền/metric functions; sheet Thông tin ghi draft/kỳ/as_of/ID bộ lọc và
  ý nghĩa ô trống; Tổng hợp, Theo người phụ trách, Phễu, Thời gian ở bước,
  CV theo ngày, Hoạt động, Hoạt động theo người. Unicode Việt, header đậm,
  freeze hàng đầu, auto-filter. Số là numeric; undefined để ô trống; tên
  recruiter luôn OOXML string, không biến thành formula/hyperlink. Không có
  dữ liệu ứng viên và không dùng audit candidate.export của export CV T17.

Chi tiết công thức và các mặc định chưa được nghiệp vụ duyệt: spec 06,
`docs/metrics/kpi-list.md`, câu hỏi #94–#99. Không thay endpoint/schema trước
đó, không migration; không thêm giao diện T27 hay lịch gửi T28 trong T26.

## Quản trị dữ liệu
- `GET/POST /data-requests` · `POST /data-requests/{id}/execute` (admin): xoá vĩnh viễn file, text, embedding của ứng viên; giữ bản ghi ẩn danh cho thống kê
- `GET /audit-log?entity=&actor_id=` (admin)

### Contract T29 · Đồng ý, thời hạn lưu và xoá dữ liệu

- Các endpoint cần đăng nhập; mutation kiểm CSRF/Origin T04, response thành công
  `Cache-Control: no-store`. Quyền kiểm ở service. Không có public portal hay tự
  suy diễn đồng ý từ email/upload. Mọi input thừa/sai trả 422 theo envelope chung.
- POST `/candidates/{id}/consent` nhận `{consent_at, note, extend_retention?:false}`.
  consent_at bắt buộc timestamp có offset, không tương lai; note trim 1–2000 ký
  tự, HR ghi nguồn/nơi lưu bằng chứng. Recruiter cần quyền Job hiện tại, lead/admin
  xem được mọi hồ sơ. Ứng viên đã gộp/xoá/đang purge trả 404. Ghi nhận đơn thuần
  không thay hạn lưu. Lặp cùng timestamp/note không gia hạn là idempotent; timestamp
  cũ hơn hoặc dùng lại để gia hạn trả 409 CONSENT_NOT_NEW.
- `extend_retention=true` chỉ admin; cần đồng ý mới hơn bản đã ghi và trong 30 ngày
  gần đây. Hạn mới = max(hạn hiện tại, hôm nay Việt Nam) + 12 tháng lịch, kẹp ngày
  cuối tháng; xoá expired_at. Consent tương lai trả 422 INVALID_CONSENT. Trả 200
  `{id,full_name,consent_at,retention_until,expired_at,purge_pending_at,purged_at}`.
  Audit candidate.consent hoặc candidate.retention_extend chỉ ID, không note.
- GET `/settings/retention?state=expiring&q=&page=1&page_size=20` chỉ admin.
  state=expiring (hôm nay…+30 ngày inclusive), expired (trước hôm nay), all;
  loại hồ sơ đã gộp/purge xong, vẫn cho xem hồ sơ đang chờ hoàn tất xoá. q trim
  ≤200, substring literal tên; xếp hạn tăng/id. Trả `{items,total}` với DTO trên.
- POST `/data-requests` chỉ admin, nhận `{candidate_id,kind?:"delete",
  requested_by_note}`; note trim 1–2000, không cho chọn actor/status. Trả 201
  `{id,candidate_id,candidate_name,kind,requested_by_note,status,handled_by,
  handled_at,created_at}`. Một yêu cầu delete đang open/candidate; retry trả cùng
  yêu cầu. T29 chỉ tạo/thực thi delete; export được dự trữ ở model, không tự xoá
  nếu gặp kind khác. Nguồn đã gộp hoặc đã purge trả 404.
  Khi yêu cầu còn open, không cho gộp ứng viên này ở cả phía nguồn lẫn đích
  (409 DATA_REQUEST_OPEN); request/audit và đối tượng của bước xác nhận giữ nguyên.
- GET `/data-requests?page=1&page_size=20` chỉ admin, `{items,total}`; xếp
  created_at giảm/id. Tên ứng viên lấy từ Candidate, trở thành null sau purge.
- POST `/data-requests/{id}/execute` chỉ admin, là xác nhận xoá của người dùng;
  không có body. Freeze được commit trước I/O Storage; sau đó xoá file/nội dung
  và audit candidate.purge trong transaction riêng. Trả 200 DTO khi hoàn tất;
  done replay không xoá/ghi audit lần hai. Storage lỗi → 503 STORAGE_UNAVAILABLE,
  hồ sơ vẫn bị khoá và yêu cầu open, có thể thử lại; Beat cũng phục hồi trạng thái
  pending. Kind/status khác → 409 INVALID_DATA_REQUEST. Note yêu cầu bị xoá khi
  purge, giữ ID/kind/trạng thái/thời điểm/actor. Job nền xử lý xong đặt handled_by=null.
- GET `/audit-log?entity=&actor_id=&action=&system=false&page=1&page_size=20`
  chỉ admin. entity/action ≤100 và so khớp chính xác; system=true chỉ actor null.
  Trả `{items,total}`; item id/actor_id/action/entity/entity_id/occurred_at, không
  trả IP, note hay nội dung; xếp occurred_at giảm/id. Phân trang mọi danh sách
  page≥1, page_size 1–100. UI dùng `/users` admin hiện có để hiện nhãn người lọc.

ASSUMED: chi tiết thời hạn và bằng chứng tại câu hỏi #105–#108. Đây là cơ chế
theo spec sản phẩm, không phải xác nhận pháp lý cho triển khai thật.
