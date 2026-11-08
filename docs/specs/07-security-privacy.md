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
- Logging nền: khớp tên trường nhạy cảm chính xác hoặc hậu tố (`*_text`, `*_body`, `*_content`, `*_password`, `*_token`, `*_secret`, `*_secret_key`, `*_api_key`, `*_access_key`, `*_email`, `*_phone`); các trường chẩn đoán `*_id`, `*_status`, `*_count` giữ tên và vẫn lọc PII trong giá trị. Không che nhầm `context`, `Content-Type` hoặc số thập phân thành SĐT.
- Exception log giữ loại lỗi và `stack` gồm basename file, dòng, tên hàm; không giữ exception message, source line, locals hoặc đường dẫn đầy đủ. Log HTTP chỉ ghi method chuẩn, route template (hoặc `[unmatched]`), status và `duration_ms`; không ghi raw path/query, headers hoặc body.
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
- Khi `APP_ENV=prod`, từ chối `SECRET_KEY=change-me` hoặc key có độ dài UTF-8 dưới 32 byte; cung cấp key ngẫu nhiên đủ mạnh qua môi trường. Giới hạn nền này được bổ sung theo review T02 F5, xem câu hỏi #14. Dev/test vẫn dùng key giả.

## Dữ liệu trong repo
- Chỉ commit CV **giả** (`data/sample_cvs/`) và fixture giả. Không commit CV thật, dữ liệu Kaggle/Hugging Face (tải về `var/datasets/`, đã gitignore).
