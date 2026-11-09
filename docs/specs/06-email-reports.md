# 06 · Email, task và báo cáo

## Mẫu email mặc định (seed)
| key | Stage gợi ý | Nội dung chính | Gửi tự động? |
|---|---|---|---|
| `cv_received` | khi CV vào hệ thống qua email/form | Cảm ơn, đã nhận CV, thông báo xử lý dữ liệu cá nhân + cách yêu cầu xoá | Có (không cần xác nhận) nếu `IMAP_ENABLED` và ứng viên có email |
| `interview_invite` | `interview` | Thời gian, địa điểm/link, người phỏng vấn; đính kèm .ics | Không, cần xác nhận |
| `rejection` | `rejected` | Lời cảm ơn, thông báo lưu hồ sơ cho cơ hội sau | Không, cần xác nhận |
| `offer` | `offer` | Lương, ngày bắt đầu, hạn phản hồi | Không, cần xác nhận |
| `submitted_to_unit` | `submitted` | Gửi người liên hệ của đơn vị tuyển: danh sách ứng viên + link | Không, cần xác nhận |

Biến dùng trong mẫu: `candidate_name`, `job_title`, `hiring_unit_name`, `interview_time`, `interview_location`, `offer_salary`, `offer_start_date`, `recruiter_name`, `recruiter_email`, `company_name`. Render bằng Jinja2 sandbox; biến thiếu → lỗi rõ ràng ở bước xem trước, không gửi mail thiếu nội dung.

### Render và context T22

`app/email/render.py` dùng SandboxedEnvironment/StrictUndefined, xoá globals,
filters/tests và chỉ chấp nhận `{{ tên_biến }}` trong danh sách trên. Chặn cú
pháp tính toán/lặp/include/attribute trước cả parse để giới hạn chi phí. Context
chỉ chuỗi, không có ORM/callable; thiếu hoặc trắng báo tên biến bằng tiếng Việt.
Template body tối đa 20000, output thô tối đa 100000 ký tự (kiểm giới hạn trước
render), subject đầu ra một dòng tối đa 500. Không render lần hai dữ liệu biến.
Escape toàn bộ text trước khi tạo HTML; Markdown chỉ đậm/nghiêng, đoạn/xuống
dòng và danh sách `- `. Không hỗ trợ raw HTML, ảnh, URL hoặc thuộc tính HTML;
`<script>` hiển thị như văn bản. Không thêm thư viện Markdown/sanitizer.

Context đọc từ Application đã kiểm quyền và ứng viên còn hiệu lực: tên ứng viên,
Job.title, HiringUnit.name; recruiter là Application.owner_id. Company lấy tên
hiển thị trong SMTP_FROM, thiếu thì báo thiếu biến khi mẫu cần tới. Interview
chưa xoá mới nhất theo scheduled_at giảm dần/id tăng dần cung cấp thời gian
`dd/mm/yyyy HH:MM` theo TZ và địa điểm; Offer chưa xoá mới nhất theo created_at
giảm dần/id tăng dần cung cấp lương định dạng `20.000.000 đồng` (0 vẫn hợp lệ)
và ngày `dd/mm/yyyy`. Không điền giả thông tin còn thiếu.

Năm mẫu được seed khi migrate và bổ sung mẫu còn thiếu ở seed dev, không ghi
đè chỉnh sửa HR. cv_received có mục đích xử lý, giới hạn chia sẻ, lưu trữ theo
chính sách, liên hệ yêu cầu xoá và nói rõ không thay bằng chứng đồng ý. Các biến
người phỏng vấn/hạn phản hồi/link hồ sơ chưa được định nghĩa: mẫu dùng đầu mối
tuyển dụng và hướng dẫn phản hồi theo thời hạn đã thống nhất, HR bổ sung nội
dung cụ thể; không tự bịa người/ngày/link. Đính kèm ICS và gửi thư thuộc T23.

## Luồng gửi
1. Đổi stage → API trả `suggested_email` (nháp, chưa lưu).
2. UI hiện xem trước; người dùng sửa và bấm **Gửi** → `POST /email-messages` rồi `/send`.
3. Worker `send_email_message`: gửi SMTP, lưu `message_id`, `sent_at`; lỗi → `failed` + `error`, retry 3 lần (1, 5, 15 phút).
4. Ghi activity `email_sent`.
Giới hạn: tối đa 200 email/giờ (cấu hình được) để tránh bị đánh dấu spam.

## Nhận CV từ hộp mail (`poll_inbox`, mỗi 5 phút khi bật)
- Đọc mail chưa xử lý trong `IMAP_FOLDER`, lấy file đính kèm PDF/DOCX/ảnh, tạo `cv_files` với `source=email`.
- Nếu tiêu đề có mã Job dạng `[JOB-xxxx]` hoặc trùng tên Job đang mở → gắn `job_id`.
- Lưu `inbound_emails` theo `message_id` để không xử lý lặp; đánh dấu mail đã đọc.

## Task và nhắc việc
- Tạo thủ công từ màn "Việc của tôi" hoặc từ hồ sơ ứng viên.
- Tự tạo task: khi application ở `screening` quá 3 ngày không có hoạt động → task "Liên hệ ứng viên" cho owner; khi interview kết thúc chưa có kết quả sau 1 ngày → task "Cập nhật kết quả phỏng vấn".
- `remind_due_tasks` mỗi sáng 8:00: email cho mỗi người danh sách task đến hạn/quá hạn.

## KPI (định nghĩa dùng trong code; khớp `docs/metrics/kpi-list.md`)
Khoảng thời gian `[from, to)` theo giờ Việt Nam. "Người" của KPI = `owner_id` của application tại thời điểm sự kiện, trừ khi ghi khác.
| KPI | Công thức |
|---|---|
| CV mới | Số `cv_files` tạo trong khoảng (theo `uploaded_by` hoặc owner Job) |
| Đã sàng lọc | Số `stage_events` có `from_stage = new` và `to_stage` khác `new` |
| Đã gửi đơn vị tuyển | Số `stage_events` với `to_stage = submitted` |
| Phỏng vấn | Số `interviews` có `scheduled_at` trong khoảng; tách đã diễn ra / sắp tới |
| Offer | Số `offers` có `sent_at` trong khoảng |
| Nhận việc | Số `placements` tạo trong khoảng |
| Tỉ lệ chuyển đổi stage | Số application từng vào stage S+1 ÷ số từng vào stage S (theo `stage_events`) |
| Time-to-fill | Trung vị (ngày) từ `jobs.opened_at` đến `placements.created_at` |
| Thời gian ở stage | Trung vị thời gian giữa hai `stage_events` liên tiếp |
| Job trễ hạn | Job `open` có `deadline < hôm nay` và số placement < headcount |
| Doanh thu placement | Tổng `placements.fee_amount` |
| Đồng thuận AI | `agree ÷ (agree + disagree)` trong `ai_feedback` |
| Hoạt động | Số `activities` theo loại và người |

Truy vấn nằm trong `app/reports/queries.py`, mỗi KPI một hàm, có test với dữ liệu dựng sẵn và kết quả tính tay.

## Báo cáo định kỳ
- `generate_daily_report` 18:00 hằng ngày: email cho lead/admin bảng KPI trong ngày theo recruiter.
- `generate_weekly_report` 8:30 thứ Hai: KPI tuần trước, so với tuần trước nữa, top Job trễ hạn, tỉ lệ đồng thuận AI.
- Nội dung dạng bảng HTML đơn giản, kèm link mở trang Báo cáo.
