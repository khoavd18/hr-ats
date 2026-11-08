# T22 · Mẫu email
Mốc: M3 · Phụ thuộc: T19 · Spec: `06` (Mẫu email mặc định), `03` (Email), `05` (Cài đặt > Mẫu email)

## Việc cần làm
- Model + migration `email_templates`, `email_messages`; seed 5 mẫu mặc định viết sẵn bằng tiếng Việt lịch sự, ngắn gọn (mẫu `cv_received` có đoạn thông báo xử lý dữ liệu cá nhân và cách yêu cầu xoá).
- `app/email/render.py`: Jinja2 `SandboxedEnvironment`, `StrictUndefined`, Markdown đơn giản → HTML an toàn; hàm dựng context từ application.
- API CRUD mẫu + preview.
- UI soạn mẫu: ô tiêu đề, ô nội dung dạng văn bản, các nút chèn biến (hiển thị tên tiếng Việt, chèn `{{ biến }}`), xem trước với một ứng viên chọn được.

## Tiêu chí nghiệm thu
- Test: render đủ biến; thiếu biến → lỗi tiếng Việt nêu tên biến; nội dung có `<script>` bị escape; sandbox chặn truy cập thuộc tính nguy hiểm.
