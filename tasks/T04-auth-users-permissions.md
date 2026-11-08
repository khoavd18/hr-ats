# T04 · Đăng nhập, người dùng, phân quyền
Mốc: M0 · Phụ thuộc: T02, T03 · Spec: `02` (users), `03` (Auth & user), `07` (Phân quyền, Ứng dụng), `05` (Đăng nhập, Cài đặt > Người dùng)

## Việc cần làm
- Model + migration `users`. Hash argon2. Khoá 15 phút sau 5 lần sai.
- JWT access/refresh trong cookie HttpOnly; CSRF double-submit token; endpoint auth và users theo `03`.
- `app/core/permissions.py`: hàm `authorize(user, action, resource=None)` theo bảng quyền `07` (các action về Job/ứng viên dùng tạm bảng membership sẽ có ở T05 — viết interface và test cho phần user/role trước).
- Lệnh CLI `uv run python -m app.scripts.create_admin --email ... ` (hỏi mật khẩu qua stdin).
- Frontend: trang đăng nhập, bảo vệ route (chuyển về `/login` khi chưa đăng nhập), hiển thị tên + đăng xuất, trang Cài đặt > Người dùng (danh sách, tạo, đổi vai trò, khoá) cho admin.

## Tiêu chí nghiệm thu
- Test API: đăng nhập đúng/sai, khoá sau 5 lần, refresh, logout, recruiter gọi `/users` bị 403, thiếu CSRF bị 403.
- Đăng nhập trên UI rồi vào các trang được; recruiter không thấy mục Cài đặt.
