# 07 · Bảo mật và dữ liệu cá nhân

CV là dữ liệu cá nhân, thuộc phạm vi Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP. Phần pháp lý cần pháp chế xác nhận trước khi chạy thật; code phải sẵn các cơ chế dưới đây.

## Phân quyền
| Hành động | admin | lead | recruiter |
|---|---|---|---|
| Xem Job | Tất cả | Tất cả | Job là owner/member |
| Xem ứng viên trong Job | Tất cả | Tất cả | Job được phép |
| Xem kho CV (tìm kiếm) | Có | Có | Có (chỉ thông tin tóm tắt; mở CV gốc → ghi audit) |
| Đổi stage, gửi email | Có | Có | Job được phép |
| Quản lý mẫu email, đơn vị tuyển | Có | Có | Không |
| Quản lý user, yêu cầu xoá dữ liệu, audit log | Có | Không | Không |
| Báo cáo | Cả team | Cả team | Của mình |
Kiểm tra quyền ở tầng service (hàm `authorize(user, action, resource)`), có test cho từng ô của bảng.

## Dữ liệu cá nhân
- Không gửi email/SĐT gốc cho LLM (xem `04` bước 2). Chấm điểm và embedding chỉ dùng `anonymized_text`.
- Logging: filter che email, SĐT, và mọi trường có tên `text`, `body`, `cv`, `content`. Không log request body của endpoint upload/candidates.
- File CV lưu với tên ngẫu nhiên, không dùng tên gốc trong đường dẫn; tải về qua API có kiểm quyền (không public URL).
- Mã hoá ổ lưu trữ ở tầng hạ tầng (ghi trong hướng dẫn triển khai); backup DB hằng ngày.
- Đồng ý xử lý dữ liệu: `candidates.consent_at`; email `cv_received` có đoạn thông báo xử lý dữ liệu; CV upload tay mặc định `consent_at = null` và hiển thị nhắc nhở.
- Thời hạn lưu: `retention_until = ngày nhận + DATA_RETENTION_MONTHS`; job `enforce_retention` hằng ngày đánh dấu hết hạn, sau 30 ngày không gia hạn thì xoá vĩnh viễn file, text, embedding (giữ bản ghi ẩn danh cho thống kê).
- Yêu cầu xoá: admin thực thi qua `data_requests`, ghi audit.
- Export Excel và tải CV gốc đều ghi audit.

## Ứng dụng
- Mật khẩu argon2; khoá tài khoản 15 phút sau 5 lần sai.
- Cookie `HttpOnly`, `Secure` (prod), `SameSite=Lax`; CSRF token cho request thay đổi dữ liệu.
- CORS chỉ `FRONTEND_ORIGIN`.
- Upload: kiểm MIME thật (magic bytes), giới hạn kích thước, từ chối file thực thi/macro (`.docm`).
- Render email: Jinja2 sandbox, escape HTML.
- Không có secret trong repo; `.env` nằm trong `.gitignore`.

## Dữ liệu trong repo
- Chỉ commit CV **giả** (`data/sample_cvs/`) và fixture giả. Không commit CV thật, dữ liệu Kaggle/Hugging Face (tải về `var/datasets/`, đã gitignore).
