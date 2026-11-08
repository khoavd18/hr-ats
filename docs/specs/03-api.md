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

## CV & ứng viên
- `POST /cv-files` multipart, nhiều file (PDF, DOCX, JPG, PNG; tối đa 10 MB/file, 50 file/lần), tuỳ chọn `job_id` → trả kết quả từng file theo contract T07 dưới đây
- `GET /cv-files/{id}` (trạng thái xử lý) · `GET /cv-files/{id}/download` (ghi audit)
- `GET /candidates?q=&skills=&min_years=&location=&source=` → tìm kiếm kho CV (full-text) · `GET /candidates/search/semantic?q=` → tìm theo nghĩa
- `GET /candidates/{id}` (ghi audit) · `PATCH /candidates/{id}` (sửa thông tin parse sai)
- `POST /candidates/{id}/merge` {into_id} → gộp trùng
- `POST /candidates/{id}/consent` {consent_at, note}
- `DELETE /candidates/{id}` → soft delete

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
