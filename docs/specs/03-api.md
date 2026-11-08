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

## CV & ứng viên
- `POST /cv-files` multipart, nhiều file (PDF, DOCX, JPG, PNG; tối đa 10 MB/file, 50 file/lần), tuỳ chọn `job_id` → trả danh sách `cv_file` với `status=pending`
- `GET /cv-files/{id}` (trạng thái xử lý) · `GET /cv-files/{id}/download` (ghi audit)
- `GET /candidates?q=&skills=&min_years=&location=&source=` → tìm kiếm kho CV (full-text) · `GET /candidates/search/semantic?q=` → tìm theo nghĩa
- `GET /candidates/{id}` (ghi audit) · `PATCH /candidates/{id}` (sửa thông tin parse sai)
- `POST /candidates/{id}/merge` {into_id} → gộp trùng
- `POST /candidates/{id}/consent` {consent_at, note}
- `DELETE /candidates/{id}` → soft delete

## Hồ sơ ứng tuyển & pipeline
- `POST /applications` {candidate_id, job_id} → thêm ứng viên trong kho vào Job (tự xếp hàng chấm AI)
- `GET /applications/{id}` → chi tiết + kết quả AI + lịch sử stage + email + interview
- `POST /applications/{id}/move` {to_stage, note, rejected_reason?} → trả `{application, suggested_email?}`; nếu stage có mẫu email, trả bản nháp để UI hiện xem trước (không tự gửi)
- `POST /applications/{id}/undo` → hoàn tác lần đổi stage gần nhất (trong 24 giờ, đúng người đã đổi hoặc lead/admin)
- `POST /applications/{id}/ai-feedback` {verdict, corrected_level?, comment?}
- `POST /applications/{id}/rescore`
- `POST /applications/{id}/notes` {text} → activity `note`

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
