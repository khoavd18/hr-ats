# 07 · Bảo mật và dữ liệu cá nhân

CV là dữ liệu cá nhân, thuộc phạm vi Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP. Phần pháp lý cần pháp chế xác nhận trước khi chạy thật; code phải sẵn các cơ chế dưới đây.

## Phân quyền
| Hành động | admin | lead | recruiter |
|---|---|---|---|
| Xem Job | Tất cả | Tất cả | Job là owner/member |
| Tạo Job (T13) | Có, gán owner | Có, gán owner | Có, owner là mình |
| Sửa Job, quản lý thành viên (T13) | Tất cả | Tất cả | Job là owner/member |
| Đổi owner Job (T13) | Có | Có | Không |
| Xem ứng viên trong Job | Tất cả | Tất cả | Job được phép |
| Xem kho CV (tìm kiếm) | Có | Có | Có (chỉ thông tin tóm tắt; mở CV gốc → ghi audit) |
| Gộp ứng viên trong kho (T16) | Có, HR xác nhận | Có, HR xác nhận | Không |
| Đổi stage, gửi email | Có | Có | Job được phép |
| Quản lý mẫu email, đơn vị tuyển | Có | Có | Không |
| Quản lý user, yêu cầu xoá dữ liệu, audit log | Có | Không | Không |
| Báo cáo | Cả team | Cả team | Của mình |
Kiểm tra quyền ở tầng service (hàm `authorize(user, action, resource)`), có test cho từng ô của bảng.
T16: `cv_bank.search` chỉ trả DTO tóm tắt không có liên hệ, raw CV hoặc Job
membership; không cấp quyền file/chi tiết. Gợi ý kiểm owner/member Job từ DB,
bao gồm sau thu hồi quyền. `cv_bank.merge` chỉ admin/lead; kiểm cả hai ứng viên
còn hạn/chưa xoá/gộp, chuyển dữ liệu và activity metadata trong một transaction,
không suy diễn consent hoặc kéo dài retention. Giữ các kiểm tra CSRF/Origin;
quyền gộp không lấy từ request body. Chi tiết ở contract T16 spec 03.
T13: action `jobs.create` kiểm vai trò đang hoạt động; `jobs.manage` kiểm scope
owner/member từ DB như jobs.view trước khi áp dụng body. Danh sách Job lọc scope
ngay trong SQL, bao gồm total. `/jobs/options` chỉ trả id/name user/đơn vị đang
hoạt động cho form; không trả email, liên hệ hay quyền quản trị. Quản lý đơn vị
vẫn chỉ admin/lead. Chi tiết mặc định chưa chốt tại câu hỏi #52.

## Dữ liệu cá nhân
- Không gửi email/SĐT gốc cho LLM (xem `04` bước 2). Chấm điểm và embedding chỉ dùng `anonymized_text`.
- Logging: filter che email, SĐT, và mọi trường có tên `text`, `body`, `cv`, `content`. Không log request body của endpoint upload/candidates.
- Logging nền: khớp tên trường nhạy cảm chính xác hoặc hậu tố (`*_text`, `*_body`, `*_content`, `*_password`, `*_token`, `*_secret`, `*_secret_key`, `*_api_key`, `*_access_key`, `*_email`, `*_phone`); các trường chẩn đoán `*_id`, `*_status`, `*_count` giữ tên và vẫn lọc PII trong giá trị. Không che nhầm `context`, `Content-Type` hoặc số thập phân thành SĐT.
- T05 bổ sung `full_name`, `name`, `candidate_name`, `address`, `phone_number`, `date_of_birth` và các hậu tố tương ứng (`*_name`, `*_address`, ...), không phân biệt hoa/thường và coi dấu gạch ngang như gạch dưới. Áp dụng cho mapping lồng nhau, JSON, extra và chuỗi key=value. Tên logger và tên hàm trong stack vẫn là metadata chẩn đoán; không đặt dữ liệu ứng viên vào tên logger/hàm.
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
- T04 dùng Argon2id và JWT HS256 (kiểm chữ ký, issuer, audience, expiry, loại access/refresh và phiên bản so với DB). Mỗi tài khoản một phiên hoạt động; refresh xoay token, logout/đổi mật khẩu/đổi quyền/khoá thu hồi ngay cả token đã sao chép. Phiên bản cấp token được chụp trước commit để tránh cấp nhầm phiên mới khi có request đồng thời.
- CSRF double-submit có chữ ký HMAC-SHA256; sau đăng nhập, hash CSRF còn gắn với JWT. Cookie `csrf_token` đọc được để frontend gắn `X-CSRF-Token`; các cookie xác thực vẫn HttpOnly. Xem bootstrap và mã lỗi tại spec 03. Dev/test dùng cùng hostname `localhost`; triển khai web/API phải cùng hostname (reverse proxy) để frontend đọc cookie CSRF host-only. Origin phải cấu hình đúng.
- Đếm sai/khoá và refresh dùng row lock trong transaction để tránh mất cập nhật và dùng lại refresh. Thao tác quản lý user lấy advisory transaction lock trước row lock actor để tránh hai admin chỉnh nhau bị deadlock. `authorize()` từ chối action chưa biết; interface `ResourceScope` cho T05 chỉ nhận membership đã truy vấn từ DB, không nhận từ body của người dùng.
- T05: với resource model `Job`, `Candidate` hoặc `Application`, gọi `authorize(user, action, resource, session=session)`. Recruiter được kiểm Job owner hoặc tồn tại job_members bằng truy vấn DB theo ID; ứng viên cần ít nhất một application chưa xoá trong Job đó, application cũng yêu cầu ứng viên chưa xoá. `applications.owner_id` riêng không cấp quyền vào Job. Membership bị thu hồi có hiệu lực ở lần kiểm tiếp theo; không dùng owner/member trên model chưa flush để quyết định quyền. Resource Candidate chỉ dùng `job_candidates.view`, Application dùng các action trong Job, `jobs.view` yêu cầu Job. Admin/lead vẫn có quyền toàn bộ theo bảng; service phải lọc soft delete theo luồng nghiệp vụ. `ResourceScope` giữ cho service đã truy vấn DB và báo cáo; không được dựng scope từ body. Tìm kho CV chung vẫn chỉ cấp quyền tìm tóm tắt, không cấp quyền đổi stage/gửi email/xem CV gốc.
- CORS chỉ `FRONTEND_ORIGIN`.
- Upload: kiểm MIME thật (magic bytes), giới hạn kích thước, từ chối file thực thi/macro (`.docm`).
- T07: cả upload trùng, GET trạng thái và download đều kiểm quyền trong service qua `authorize`; kho CV tóm tắt không cấp quyền file gốc. File chưa gắn Job/Candidate chỉ uploader/admin/lead truy cập; file có Job/Candidate theo quyền Job upload hoặc application còn hiệu lực của ứng viên. Thu hồi membership không bị quyền uploader vượt qua. Không trả metadata bản ghi trùng nếu caller không có quyền, không phục hồi bản ghi soft delete.
- T10 (#45): khi parse gắn Candidate vào file chưa có Job, uploader vẫn đọc đúng file đã tải. Không cấp quyền đọc các file khác cùng Candidate, chi tiết Candidate, đổi stage hay email; file có Job vẫn kiểm scope Job/application như trước. Candidate/file đã xoá vẫn bị chặn trong service. Test hai recruiter cùng email ứng viên chứng minh mỗi người chỉ đọc được file riêng khi chưa có Job.
- T07: tên gốc chỉ lưu metadata (bỏ đường dẫn/ký tự điều khiển, tối đa 255 ký tự), không dùng cho path/header download hoặc log. Download dùng attachment tên theo UUID, nosniff, no-store; chỉ ghi audit sau khi đọc storage thành công và commit audit trước khi trả byte. GET metadata cũng có audit. DOCX kiểm content types và VBA, giới hạn cấu trúc/giải nén trước đọc ZIP; không extract ra filesystem. Chi tiết contract tại spec 03.
- Render email: Jinja2 sandbox, escape HTML.
- Không có secret trong repo; `.env` nằm trong `.gitignore`.
- Khi `APP_ENV=prod`, từ chối `SECRET_KEY=change-me` hoặc key có độ dài UTF-8 dưới 32 byte; cung cấp key ngẫu nhiên đủ mạnh qua môi trường. Giới hạn nền này được bổ sung theo review T02 F5, xem câu hỏi #14. Dev/test vẫn dùng key giả.

## Dữ liệu trong repo
- Chỉ commit CV **giả** (`data/sample_cvs/`) và fixture giả. Không commit CV thật, dữ liệu Kaggle/Hugging Face (tải về `var/datasets/`, đã gitignore).
