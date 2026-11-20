# 09 · Nhắc việc quá hạn qua n8n

Dự án cá nhân dùng n8n Community Edition local và một chat Telegram riêng.
Celery tạo bản nhắc lúc 8:00 giờ Việt Nam khi tích hợp được bật. Mỗi ngày có
tối đa một bản nhắc cho tài khoản đã chọn. Nguồn đếm là mục **Việc của tôi**
của tài khoản đang hoạt động, với quyền Job hiện hành tại lúc chụp số đếm.
Chỉ đếm việc `todo` hoặc `doing` có `due_at` trước lúc chạy. Số 0 bỏ qua.

## Webhook

Workflow local dùng **Production URL** và Header Auth `X-HR-ATS-Key`.
Celery POST đúng bốn trường sau.

```json
{
  "event_id": "c8db9a82-3a46-4c62-9b4c-21b987819570",
  "event_type": "task.overdue_summary",
  "version": 1,
  "overdue_count": 1
}
```

Sau khi Telegram gửi thành công, **Respond to Webhook** trả HTTP 2xx và JSON
như dưới đây. Nếu node Telegram lỗi, cấu hình node ở chế độ dừng workflow.

```javascript
{{ { received: true, event_id: $('Webhook').first().json.body.event_id } }}
```

Đặt **Respond With** thành **JSON** và **Response Body** thành **Expression**.
Tên `Webhook` trong biểu thức phải khớp với tên node nhận HTTP.

PostgreSQL giữ bản nhắc và trạng thái gửi. Beat gọi worker mỗi phút để lấy
một bản đến lượt. Khi thiếu phản hồi hợp lệ, worker gửi lại cùng ID và số
đếm sau 1, 5, 15 phút, rồi mỗi 15 phút trong cùng ngày theo giờ Việt Nam.
Bản nhắc hết hạn lúc nửa đêm để tránh hiển thị số đếm cũ như số hôm nay.
Số đếm thuộc thời điểm tạo bản nhắc. Nếu Telegram đã nhận tin
nhưng ATS mất phản hồi, workflow lab có thể gửi trùng ở lần thử lại. Khi mở
rộng tích hợp cần xử lý ID lặp phía nhận. Thông tin kết nối nằm trong cấu
hình môi trường của người vận hành. Payload không có dữ liệu ứng viên,
tên việc hoặc định danh tài khoản ATS.

Trong **Workflow settings** của n8n, tắt lưu execution thành công, execution
lỗi, execution thủ công và tiến độ từng node. Node Webhook xử lý header xác
thực, nên để lịch sử gửi trong ATS. [Tài liệu cấu hình n8n](https://docs.n8n.io/build/manage-workflows/configure-workflow-settings#save-failed-production-executions)

## Bật và thử trên máy

1. Dùng workflow n8n local đã publish và chat Telegram của chính tài khoản
   ATS sẽ chọn. Trong trình duyệt đã đăng nhập ATS, xem response của
   `GET /api/v1/auth/me` tại **DevTools → Network** và chép trường `id`.
2. Điền bốn dòng dưới đây vào `.env` ở gốc repo. Dùng cổng và đường dẫn
   thực tế, khóa Header Auth của webhook và UUID vừa lấy. Với worker trong
   Docker Desktop gọi về máy host, dùng `host.docker.internal` trong URL.

   ```dotenv
   N8N_OVERDUE_ENABLED=true
   N8N_OVERDUE_WEBHOOK_URL=http://127.0.0.1:5678/webhook/hr-ats/task-overdue
   N8N_OVERDUE_WEBHOOK_KEY=
   N8N_OVERDUE_USER_ID=
   ```

3. Tại `backend/`, chạy `uv run alembic upgrade head`. Sau đó khởi động
   lại Celery worker và Beat theo README để nạp cấu hình mới.
4. Trong ATS dev, dùng tài khoản đã chọn và tạo một việc giả đã quá hạn
   cùng một việc giả còn hạn. Thử vào một ngày chưa tạo bản nhắc cho tài
   khoản này. Với worker đang chạy, từ `backend/` gọi:

   ```powershell
   uv run celery -A app.workers.celery_app call queue_overdue_webhook
   ```

   Beat sẽ đẩy bản nhắc trong lượt kiểm tra tiếp theo, khoảng một phút.
   Nếu đang thử chỉ với worker, chờ worker ghi log hoàn thành tác vụ trên
   rồi gọi `uv run celery -A app.workers.celery_app call deliver_overdue_webhook`.
   Telegram báo **1 việc quá hạn** nếu đó là việc quá hạn duy nhất của tài
   khoản. Gọi lại cả hai tác vụ trong ngày để kiểm chống gửi lại.
5. Muốn tạm dừng, đặt `N8N_OVERDUE_ENABLED=false` rồi khởi động lại worker
   và Beat. Các tác vụ email hiện có dùng lịch và cấu hình riêng.
