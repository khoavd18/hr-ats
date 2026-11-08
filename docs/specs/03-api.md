# 03 · API

Base `/api/v1`. JSON, xác thực bằng cookie HttpOnly chứa JWT (access 30 phút, refresh 7 ngày). Mọi endpoint (trừ login, health) yêu cầu đăng nhập. Quyền theo `07-security-privacy.md`. OpenAPI tự sinh tại `/docs` (chỉ bật khi `APP_ENV != prod`).

## Hệ thống
- `GET /health` → HTTP 200 `{"status":"ok","db":"ok","redis":"ok"}` khi truy vấn DB và Redis ping đều thành công. Nếu một trong hai không khả dụng: HTTP 503 `{"error":{"code":"SERVICE_UNAVAILABLE","message":"Dịch vụ tạm thời không khả dụng."}}`; không trả lỗi kết nối nội bộ.
- `GET /config/public` → nhãn đơn vị tuyển, danh sách stage và nhãn tiếng Việt. Trong T02 chưa có stage: chỉ trả `{"hiring_unit_label":"Đơn vị tuyển"}` theo `HIRING_UNIT_LABEL`; chưa trả thông tin nghiệp vụ hoặc secret. Xác thực được triển khai tại T04 theo quy tắc chung ở đầu spec.

### Chuẩn lỗi nền (T02)

Các lỗi dùng `{"error":{"code":"...","message":"<tiếng Việt>"}}`: `AppError` giữ code/message/status do service định nghĩa; validation dùng `VALIDATION_ERROR` (422); không tìm thấy dùng `NOT_FOUND` (404); sai method dùng `METHOD_NOT_ALLOWED` (405); lỗi ngoài dự kiến dùng `INTERNAL_ERROR` (500). Không phản chiếu input validation, exception detail hoặc stack trace. Preflight CORS bị từ chối dùng `CORS_REJECTED` (400); origin được cho phép vẫn chỉ là `FRONTEND_ORIGIN`.

## Auth & user
- `POST /auth/login` {email, password} · `POST /auth/logout` · `POST /auth/refresh` · `GET /auth/me`
- `POST /auth/change-password`
- `GET/POST /users`, `PATCH /users/{id}` (admin): tạo, đổi vai trò, khoá

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
