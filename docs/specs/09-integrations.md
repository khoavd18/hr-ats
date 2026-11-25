# 09 · Tích hợp n8n

## Quyết định T34

- VERIFIED: W5 đang dùng n8n Community Edition self-host local và một chat
  Telegram riêng. HR dùng Gmail và Zalo. Đợt demo dùng Telegram cho các
  thông báo và báo cáo W4.
- UNKNOWN: Gmail cá nhân hay Google Workspace, nguồn CV thật và đích Zalo
  khi triển khai. Danh sách sự kiện nghiệp vụ yêu cầu gồm `cv.scored`,
  `application.stage_changed`, `interview.scheduled`, `interview.cancelled`,
  `task.overdue` và `report.daily_ready`.
- VERIFIED: hướng dẫn n8n cho phép dùng Community Edition self-host cho
  workflow nội bộ. Việc host n8n như một dịch vụ hoặc cho khách ngoài tổ
  chức tạo hay cấu hình workflow cần giấy phép thương mại. Cần xác nhận
  với n8n trước khi đưa mô hình bán cho khách vào phạm vi triển khai.
  [Hướng dẫn giấy phép n8n](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case)
- VERIFIED: SAML SSO thuộc Business/Enterprise và external secrets thuộc
  Enterprise theo tài liệu n8n. Demo Community Edition dùng credential
  được mã hóa của n8n. [SAML](https://docs.n8n.io/administer/manage-users-and-access/verify-user-identity/use-saml/)
  [External secrets](https://docs.n8n.io/administer/manage-credentials/use-external-secret-stores/)

## Hợp đồng outbox T35

- Mỗi bản giao có một UUID v4 `event_id`, `event_type`, `version: 1` và
  `data` theo schema cố định. `integration.test` có `data: {}`.
  `task.overdue_summary` có `data: {"overdue_count": 1}` với số nguyên dương.
  `task.overdue_summary` là tên của bản thử T34. T39 bổ sung schema sự kiện
  nghiệp vụ có ID nội bộ, stage, mức AI và link hồ sơ theo nhu cầu của thông
  báo. Link dùng tuyến ATS có đăng nhập và kiểm quyền hiện hành.
- Celery ký UTF-8 của chuỗi
  `ASCII(timestamp) + "." + ASCII(path) + "." + raw_body` bằng HMAC-SHA256.
  Gửi timestamp Unix giây qua `X-HR-ATS-Timestamp` và chữ ký dạng
  `v1=<lowercase hex>` qua `X-HR-ATS-Signature`. Receiver so sánh hằng
  thời gian trước khi đọc JSON, chấp nhận lệch đồng hồ tối đa 300 giây,
  rồi chống xử lý lại theo `event_id`. Khóa ký nằm trong cấu hình vận hành.
- Lặp lại cùng bản giao sau 1, 5, 15 phút nếu thiếu ACK. Mỗi lần ký lại với
  timestamp hiện tại, giữ nguyên ID và nội dung. HTTP 2xx với JSON
  `{"received": true, "event_id": "..."}` xác nhận đã xử lý. Hết bốn lượt
  chuyển sang thất bại để quản trị xem ở T38.
- Chỉ gửi tới origin n8n do vận hành đặt, với path production
  `/webhook/hr-ats/…`. Dùng HTTPS khi triển khai, cho phép HTTP loopback
  khi phát triển. Không theo redirect. T35 chạy opt-in. Workflow Header
  Auth của W5 dùng hợp đồng cũ đến khi T39 chuyển sang HMAC.

## Token và ranh giới dữ liệu

T36 dùng principal `integration` riêng, token ngẫu nhiên băm khi lưu, có
scope theo phương thức và đường dẫn, hết hạn hoặc thu hồi được, có giới
hạn tần suất và audit tối thiểu. Token được gắn với tài khoản ATS đang hoạt
động. Tạo việc và đọc báo cáo vẫn kiểm quyền nghiệp vụ của tài khoản đó.
Token dịch vụ và khóa HMAC phục vụ hai chiều xác thực riêng.

| Scope | Endpoint | Quyền |
|---|---|---|
| `tasks:create` | `POST /api/v1/integrations/tasks` | Tạo việc và trả ID của việc vừa tạo |
| `reports:summary` | `GET /api/v1/integrations/reports/summary` | Đọc số liệu tổng hợp |
| `cv:upload` | `POST /api/v1/integrations/cv-files` | Dành cho T42, trả 403 đến khi có duyệt và luồng consent |

Người vận hành cấp và thu hồi token trên máy chủ bằng
`uv run python -m app.scripts.integration_token` tại `src/backend/`.
Lệnh `issue` nhận `--sponsor <user_uuid>`, một hoặc nhiều `--scope` và
`--expires-in-days <1..365>`. Lưu đầu ra token một lần vào kho bí mật;
ID thu hồi được ghi riêng qua stderr. Lệnh `revoke <token_id>` thu hồi
ngay cho các request sau đó. Giới hạn mặc định 30 request/phút/token.

n8n có thể gửi thông báo nội bộ và xuất số liệu tổng hợp đã duyệt. Payload
chỉ dùng trường có trong schema của sự kiện. CV, tên ứng viên, email,
điện thoại, ghi chú tự do và ID ứng viên trực tiếp không đi vào webhook
hay nhật ký gửi. Link hồ sơ phải đi qua xác thực, phân quyền trong ATS.
n8n không trực tiếp truy cập DB ATS, đổi stage, gửi email từ chối, gửi
offer, xóa hồ sơ hoặc tự quyết định loại ứng viên. T41–T43 cần duyệt riêng.

## W5 hiện tại · Nhắc việc quá hạn qua n8n

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

3. Tại `src/backend/`, chạy `uv run alembic upgrade head`. Sau đó khởi động
   lại Celery worker và Beat theo README để nạp cấu hình mới.
4. Trong ATS dev, dùng tài khoản đã chọn và tạo một việc giả đã quá hạn
   cùng một việc giả còn hạn. Thử vào một ngày chưa tạo bản nhắc cho tài
   khoản này. Với worker đang chạy, từ `src/backend/` gọi:

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
