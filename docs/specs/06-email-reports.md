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
`dd/mm/yyyy HH:MM` theo APP_TIMEZONE và địa điểm; Offer chưa xoá mới nhất theo created_at
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

### Gửi và xác nhận T23

Worker ở queue `email`, payload chỉ UUID message, ID lượt gửi, mốc scheduled_for
và số retry; không có địa chỉ/nội dung/lịch trong Celery args hoặc log. Worker
chỉ nhận queued hoặc failed còn lịch retry, ID lượt gửi và mốc hẹn phải khớp DB.
Huỷ/gửi lại làm job cũ mất hiệu lực; delivery lặp sau sent không có tác dụng.
Trước SMTP, kiểm lại user đang hoạt động, quyền Job và eligibility ứng viên.
Không dùng AI hay tự đổi stage/offer status khi gửi thư.

SMTP smtplib có timeout 15 giây, STARTTLS với context xác minh chứng chỉ khi
SMTP_TLS=true, login chỉ khi có SMTP_USER. MIME có text và HTML an toàn; lưu
Message-ID/sent_at, activity email_sent chỉ email_message_id và ID liên quan.
Exception SMTP không được lưu/log; UI dùng thông báo Việt cố định. SMTP thất
bại → failed, scheduled_for hẹn 60/300/900 giây; hết ba retry thì null. Hẹn retry
qua Celery sau commit, không sleep worker; eager test lưu trạng thái, các test
retry điều khiển trực tiếp task và kiểm countdown (không chờ 21 phút).

Giới hạn toàn hệ thống `EMAIL_RATE_LIMIT_PER_HOUR=200` (số nguyên dương): đếm
thư đã được SMTP chấp nhận trong một giờ trượt, kể cả message sau này bị ẩn.
Advisory transaction lock PostgreSQL dùng chung các worker, giữ qua gửi/commit;
đủ hạn mức thì giữ queued, hẹn tới khi thư cũ nhất ra khỏi cửa sổ. Không tiêu
hao lượt retry SMTP khi chờ hạn mức. Ở quy mô 200/giờ, chọn tuần tự hoá delivery
để không thêm bảng đếm/service/dependency.

Interview invite gắn lịch chưa xoá mới nhất theo scheduled_at/id như context
T22, dùng calendar_file T21 (TZID/UID/thời lượng/địa điểm, không attendee/CV).
Kiểm có lịch khi preview/tạo nháp/send; sinh ICS từ thông tin hiện tại ngay
trước SMTP và kiểm lại quyền. UI nói rõ lịch dùng thông tin hiện tại khi gửi;
không tạo lịch giả nếu thiếu. Body/recipient đã HR duyệt được giữ nguyên.

Dialog cho sửa người nhận/tiêu đề/nội dung, Gửi mới tạo draft rồi send, Không
gửi/Escape trước lưu không tạo message. Sau lỗi send giữ draft ID, khoá sửa
để retry không tạo thêm nháp; Không gửi lúc này huỷ nháp đã lưu. Drawer có mục
Email: lịch sử phân trang/polling, xem thư trong iframe sandbox/CSP, trạng thái
và huỷ/gửi lại, soạn tự do hoặc render mẫu đang bật. Mỗi nút Gửi/Gửi lại đều
là hành động HR sau xem trước; không có luồng auto-send cho bốn mẫu cần duyệt.

Giới hạn SMTP: nếu server đã nhận thư nhưng kết nối/tiến trình mất trước khi
ghi sent vào DB, không thể bảo đảm exactly-once chỉ bằng SMTP. Retry giữ cùng
Message-ID trong một lượt xác nhận để hỗ trợ đối chiếu; không tuyên bố server
nhận thư sẽ tự chống trùng. Không tự retry lỗi DB sau khi SMTP đã trả thành công.

## Nhận CV từ hộp mail (`poll_inbox`, mỗi 5 phút khi bật)
- Đọc mail chưa xử lý trong `IMAP_FOLDER`, lấy file đính kèm PDF/DOCX/ảnh, tạo `cv_files` với `source=email`.
- Nếu tiêu đề có mã Job dạng `[JOB-xxxx]` hoặc trùng tên Job đang mở → gắn `job_id`.
- Lưu `inbound_emails` theo `message_id` để không xử lý lặp; đánh dấu mail đã đọc.

### Contract triển khai T24

- `app/email/inbound.py` đăng ký task poll_inbox ở queue email. Beat chỉ có lịch
  300 giây khi IMAP_ENABLED=true; task cũng kiểm cờ trước kết nối. IMAP4_SSL
  cổng chuẩn 993, context xác minh chứng chỉ và timeout 15 giây, login bằng biến
  môi trường; folder được quote. UID SEARCH UNSEEN, kiểm RFC822.SIZE trước khi
  tải BODY.PEEK[]; chỉ đánh dấu Seen sau commit DB. Không di chuyển/xoá mail.
- ASSUMED (#86–#89): tối đa 100 mail/lượt, 50 MiB/mail, 50 attachment/mail;
  mỗi file dùng giới hạn 10 MiB và magic-byte/macro validator T07. Tệp không hợp
  lệ bỏ qua riêng, ghi error cố định; không có tệp hợp lệ → ignored (thư không
  attachment có count=0), còn lại processed. File có tên nhưng inline cũng được
  kiểm như attachment; không lưu body. Thư quá lớn giữ unread và báo lỗi trạng
  thái để quản trị xử lý, không tải payload. Lỗi storage/DB rollback marker và
  file, dọn object vừa ghi; thư giữ unread để lượt sau thử lại.
- Mã Job là 8 hex đầu UUID, UI viết hoa, so không phân biệt hoa thường. Chỉ Job
  open, duy nhất một mã khớp hoặc toàn subject trùng tên sau NFC/casefold/gộp
  khoảng trắng. Mã không rõ/va chạm/nhiều mã hoặc tên trùng → kho CV chung,
  không đoán Job. Không tự thêm thành viên hoặc đổi stage.
- Message-ID thiếu dùng `sha256:` của MIME gốc; cùng ID không tiếp nhận lần hai.
  Advisory transaction lock theo Message-ID và hash file (sort hash) chống
  đọc đồng thời. Cùng hash có sẵn thì giữ record/quyền/Job/nguồn cũ như T10,
  không parse lại hoặc gửi thêm receipt. Marker và tất cả file commit cùng
  transaction. Sau đó recover_intake publish pending file; lượt poll sau còn
  quét pending/receipt queued để phục hồi crash giữa commit và publish.
- Hook sau commit parse thành công tạo một EmailMessage có ID bằng CvFile.id,
  chỉ source=email và template key=cv_received đang bật, không yêu cầu xác
  nhận. Không dùng From làm địa chỉ ứng viên. Chỉ email được trích từ CV qua
  redaction cục bộ; Candidate mới source=email, không tự tạo consent. Context
  có Job thì dùng Job/đơn vị/owner; không có Job dùng nhãn chung “cơ hội tuyển
  dụng” và admin active đầu tiên theo UUID. Company từ tên SMTP_FROM. Thiếu
  admin/email/biến mà mẫu cần hoặc template ngừng dùng → chưa tạo receipt,
  không điền giả dữ liệu. Lượt poll sau có thể thử lại khi đã bổ sung dữ liệu.
- Worker gửi kiểm lại feature flag, nguồn/file done/chưa xoá và eligibility,
  email hiện tại đúng recipient, key/template vẫn bật/không yêu cầu xác nhận,
  created_by đang active. Dùng chung SMTP, rate limit và retry T23; delivery lặp
  sau sent không gửi lại, bốn mẫu cần người duyệt vẫn giữ luồng T23. Activity
  chỉ ID, actor=null. Không bảo đảm exactly-once trong cửa sổ SMTP nhận thư rồi
  tiến trình/DB lỗi trước commit, cùng giới hạn đã công bố ở T23.
- Trạng thái lần poll gần nhất lưu Redis, lỗi chỉ mã cố định; thành công xoá mã
  lỗi lượt trước. API admin/lead và tab Kết nối hộp mail dịch tiếng Việt, poll
  trạng thái 30 giây. Cấu hình vẫn qua env, không trả credentials/metadata thư.

## Task và nhắc việc
- Tạo thủ công từ màn "Việc của tôi" hoặc từ hồ sơ ứng viên.
- Tự tạo task: khi application ở `screening` quá 3 ngày không có hoạt động → task "Liên hệ ứng viên" cho owner; khi interview kết thúc chưa có kết quả sau 1 ngày → task "Cập nhật kết quả phỏng vấn".
- `remind_due_tasks` mỗi sáng 8:00: email cho mỗi người danh sách task đến hạn/quá hạn.

### Chi tiết triển khai T25

Beat dùng Asia/Ho_Chi_Minh, enable_utc=true. generate_followup_tasks ở queue
default mỗi giờ, remind_due_tasks queue email bằng crontab 8:00; độc lập cờ
IMAP. Chạy đúng một Beat với cùng cấu hình DB/broker như worker.

Screening: đã ở bước này >72 giờ và không có Activity chưa ẩn của Application
trong 72 giờ gần nhất. Interview pending: scheduled_at + duration_minutes đã
qua >24 giờ, Application còn ở bước mở new…offer. Đúng biên chưa tạo; không
tự từ chối/đổi stage. Assignee và created_by là owner Application đang active,
còn quyền Job; ứng viên/hồ sơ phải eligible. due_at là thời điểm tạo. Cùng
Application/title cố định có task todo/doing chưa ẩn thì không tạo thêm, kể
cả task tạo tay; done/cancelled cho phép tạo việc mới nếu điều kiện vẫn đúng.
Không thêm cột loại; sửa title việc tự động làm nó không còn được coi là cùng
loại. Generator giữ advisory transaction lock, ghi cả lượt cùng transaction.

Email nội bộ chỉ người active có task todo/doing eligible, due_at trước nửa
đêm ngày mai Việt Nam (gồm quá hạn và hết hôm nay); không nhắc task không hạn.
Mỗi người một EmailMessage/ngày, ID tất định từ user/ngày và đánh dấu version
4 để tương thích allowlist metadata. created_by là người nhận; application_id/
template_id null. API tạo thư vẫn bắt buộc Application và không nhận ID/mốc/
message_id, không thể tự cấp marker thư hệ thống. Marker phải khớp đủ ID,
created_at/người nhận và Message-ID trước khi worker áp dụng nhắc nội bộ.

Producer commit trước publish, chạy lại cùng ngày giữ ID, queued được publish
lại an toàn; sent không gửi lại. Worker kiểm user active/email hiện tại, lọc
lại quyền Job/eligibility/task mở/hạn và dựng lại nội dung trước SMTP; không
còn việc thì failed, không gửi thư rỗng. Nội dung chỉ title (escape HTML) và
hạn, không đọc CV/email ứng viên; không có payload/nội dung trong Celery args.
Dùng chung SMTP/rate limit/retry/checkpoint T23, activity email_sent actor null
chỉ email_message_id. Publish lỗi giữ queued; có thể chạy lại remind_due_tasks
trong ngày để phục hồi, không gọi SMTP trực tiếp. Giới hạn exactly-once SMTP
như T23. Thư nội bộ này không thay luồng HR duyệt offer/từ chối ứng viên.

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

### Contract triển khai KPI T26/v1 — status: draft

ASSUMED: chi tiết dưới đây là mặc định kỹ thuật theo #94–#99, chờ HR duyệt;
không nâng danh sách KPI thành approved. API trả definition_status=draft.
Nguồn tổng hợp là fact trong PostgreSQL; SQL count/sum/distinct/percentile_cont,
không gọi LLM. Mỗi hàm nhận session/start/end/filters; grouped=True tính cả
bảng recruiter bằng truy vấn nhóm, không gọi lại bộ KPI cho từng người.

**Kỳ và quyền:** from/to là ngày YYYY-MM-DD, 1–366 ngày, to không bao gồm.
Chuyển hai mốc nửa đêm Asia/Ho_Chi_Minh sang UTC trước WHERE; không phụ thuộc
TZ của máy hoặc phiên DB. Chỉ 366 ngày mỗi request để giới hạn bảng theo ngày.
Admin/lead xem toàn bộ, recruiter mặc định và bắt buộc của mình; truyền ID
người khác → 403. Bộ lọc recruiter/Job/đơn vị giao nhau. Recruiter còn phải
có quyền owner/member Job hiện tại, kể cả sau khi thu hồi membership. Fact
không gắn Job chỉ có trong báo cáo không lọc Job/đơn vị, và vẫn lọc attribution.

**Attribution:** Application.owner_id được gán lúc tạo và hiện không có API
đổi owner; dùng owner này cho stage/interview/offer/placement/feedback, không
dùng actor đổi bước hoặc user viết feedback. Nếu sau này có chuyển owner phải
thêm lịch sử trước khi khẳng định attribution tại thời điểm sự kiện. CV ưu tiên
uploaded_by, null thì owner Job hiện tại; cả hai null vào hàng chưa gán. Job
trễ hạn theo owner Job hiện tại. Hoạt động theo actor_id, null vào hệ thống.
Job đổi owner/đơn vị có thể làm đổi nhóm lịch sử vì chưa có lịch sử phân công
Job. Không bịa owner cũ. Bảng team giữ cả user inactive có dữ liệu; có hàng 0
cho recruiter chưa có số liệu và hàng admin/lead nếu có đóng góp. Hàng null
được giữ để đối chiếu tổng, không âm thầm bỏ activity/CV tự động.

**Grain và thời điểm:**
- CV đếm file chưa ẩn theo created_at, không đếm candidate/application, không
  join một file với mọi Application để tránh nhân bản. Tất cả trạng thái parse.
- Screen đếm event from_stage=new và to_stage khác new; gửi đơn vị đếm event
  to_stage=submitted, theo occurred_at. Lượt đi lại/hoàn tác vẫn là sự kiện thật
  theo spec 02, không triệt tiêu. Không suy ra từ stage hiện tại.
- Interview theo scheduled_at: elapsed khi < as_of, upcoming khi >= as_of.
  elapsed chỉ nghĩa lịch đã đến giờ, không khẳng định đã diễn ra (result có
  thể pending/no_show). Không lọc theo created_at hoặc kết quả phỏng vấn.
- Offer theo sent_at (draft null không tính); accepted/declined vẫn tính nếu
  đã có sent_at trong kỳ. Placement theo created_at, mọi status chưa ẩn,
  không phải start_date; phí cùng population đó, đơn vị VND.
- Feedback lấy verdict hiện tại của row chưa ẩn theo created_at; upsert T15
  giữ created_at, không tạo lịch sử mỗi lần sửa. Sửa verdict có thể làm thay
  đổi báo cáo kỳ cũ; không coi đây là phép đo accuracy từ nhãn chuẩn.
- Activity theo occurred_at, nhóm type/actor; liên kết Job dùng job_id hoặc
  Job của Application nếu job_id null. Không đọc payload/ghi chú/liên hệ.

**Phễu và trung vị:** mỗi Application chỉ đếm một lần ở mỗi to_stage trong kỳ,
nhưng có thể xuất hiện ở nhiều bước. Không ép chung cohort: S+1/S là tỉ lệ dòng
vào trong kỳ, có thể >1 nếu các hồ sơ đã vào S trước kỳ; không clamp 100%.
Trả đủ tám bước; chỉ chuỗi new→screening→submitted→interview→offer→hired có
bước kế. rejected/withdrawn/hired không có bước kế, rate=null. Mẫu số=0 cũng
null, kèm count/next_count để UI giải thích.

T12 chưa ghi StageEvent khởi tạo: khi không có event from=null/to=new còn
hiệu lực, truy vấn thêm entry new ảo tại Application.created_at; không ghi hay
backfill DB. Entry thực có ưu tiên nếu tồn tại. Thời gian ở stage dùng entry
thật/ảo và lead theo application, sắp occurred_at rồi created_at/id; entry ảo
đứng trước event thật khi cùng thời điểm. Mẫu được gán vào kỳ của **exit**,
entry có thể trước from. Đọc lịch sử trước khi lọc kỳ; lượt chưa thoát không
tính. Một application đi lại tạo nhiều mẫu; thời lượng bằng 0 vẫn hợp lệ.
Trả đủ tám bước, mỗi bước days/sample_count/excluded_count (hiện duration
không có mẫu âm vì sắp theo thời gian, excluded_count=0).

Time-to-fill lấy placement trong kỳ, days=(created_at−opened_at)/86400 giây,
trung vị liên tục PostgreSQL (mẫu chẵn lấy trung bình hai giá trị giữa).
opened_at thiếu hoặc sau placement (Job mở lại) không gán 0; trả excluded_count.
Không có mẫu hợp lệ → days=null. Team tính từ mẫu gốc, không trung bình trung
vị từng người. Độ chính xác trả về không làm tròn; format thuộc UI T27.

**Snapshot và dữ liệu thiếu:** Job trễ hạn dùng trạng thái/deadline/headcount và
mọi placement chưa ẩn của Job trong DB hiện tại, không lọc kỳ/recruiter trước
khi tính số ghế đã nhận. Deadline < ngày Việt Nam của as_of; đúng hôm nay
chưa trễ. as_of được chụp một lần mỗi request để các nhánh dùng cùng ngày;
đây không phải truy vấn trạng thái lịch sử tại to. Các truy vấn đọc dữ liệu
hiện tại theo transaction mặc định; không cung cấp snapshot lưu trữ lịch sử.
Count không có sự kiện là 0; rate/median không xác định là null. Phí trả
amount/known_count/missing_count: sum phần đã biết, không có phí đã biết là
null, không biến phí thiếu thành 0. Luôn giữ số mẫu khi rollup.

Loại fact bị soft delete và con của Application bị soft delete. Không đọc
Candidate/PII hoặc phụ thuộc retention của CV để tính số thống kê tổng hợp;
thống kê từ các fact còn giữ được tiếp tục tính sau khi hồ sơ hết hạn/ẩn danh.
Gộp có Application bị ẩn thì bỏ các fact của Application đó; T29 chịu trách
nhiệm bảo toàn thống kê ẩn danh khi thiết kế xoá thật. Không xuất tên/liên hệ
ứng viên, CV text hoặc payload; Excel chỉ số tổng hợp và tên recruiter.

## Báo cáo định kỳ
- `generate_daily_report` 18:00 hằng ngày: email cho lead/admin bảng KPI trong ngày theo recruiter.
- `generate_weekly_report` 8:30 thứ Hai: KPI tuần trước, so với tuần trước nữa, top Job trễ hạn, tỉ lệ đồng thuận AI.
- Nội dung dạng bảng HTML đơn giản, kèm link mở trang Báo cáo.
