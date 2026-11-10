# 02 · Mô hình dữ liệu

Mọi bảng có `id uuid pk` (UUID v4 do ứng dụng cấp), `created_at timestamptz default now()`, `updated_at timestamptz default now()` (SQLAlchemy cập nhật khi sửa bản ghi). Bảng có dữ liệu ứng viên có thêm `deleted_at timestamptz null` (soft delete). Tên bảng/cột tiếng Anh, snake_case.

### Chi tiết triển khai T05
- T05 tạo đúng 10 bảng lõi bên dưới và tái sử dụng `users` từ T04; các bảng interview/offer/placement/task/email/data_requests do task sau tạo. Enum Python có đủ giá trị trong spec; migration chỉ tạo enum PostgreSQL được bảng lõi sử dụng.
- `deleted_at` có trên `candidates`, `cv_files`, `applications`, `stage_events`, `ai_feedback`, `activities`. `audit_log` chỉ chứa định danh và metadata truy cập, không có nội dung CV hay soft delete. FK mặc định RESTRICT/NO ACTION, không cascade xoá cứng.
- Bắt buộc các định danh/FK nghiệp vụ (trừ các FK ghi rõ null), tên/tiêu đề, mô tả Job, loại đơn vị, nguồn ứng viên và `retention_until`. Thông tin liên hệ, nội dung parse, AI chưa xử lý và mô tả tuỳ chọn được null. `consent_at` luôn null nếu bên gọi chưa cung cấp bằng chứng. Tính thời hạn lưu thuộc service tiếp nhận/T29; model không tự suy diễn đồng ý.
- Giá trị mặc định: Job `draft`, `headcount=1`, CV/application AI `pending`, application `new` và `stage_entered_at=now()`, nguồn ứng viên `upload`, các mảng JSON `[]`, activity payload `{}`, đơn vị tuyển đang hoạt động. Không có hành động AI tự đổi stage.
- CHECK: email ứng viên lowercase; kinh nghiệm/lương/kích thước file không âm; headcount/page_count dương nếu có; salary_min ≤ salary_max khi có cả hai; ai_score 0–100 nếu có; feedback verdict `agree`/`disagree`. UNIQUE feedback `(application_id, user_id)` để upsert; UNIQUE job member `(job_id, user_id)`; SHA-256 unique kể cả file đã soft delete.
- Index FK phục vụ tra quyền và lịch sử; unique application có điều kiện cũng phục vụ tra cứu theo candidate_id. Chưa áp dụng migration dữ liệu hay thay đổi bảng `users`.
- Schema đọc tại `app/schemas/core.py` không xuất embedding/search_tsv, đường dẫn storage, text CV, parsed_json hoặc lỗi parse thô. Đây là schema nội bộ cho các task API tiếp theo, chưa mở endpoint mới; kho CV chung phải dùng schema tóm tắt riêng và kiểm quyền trước khi đọc chi tiết/tải file.

## Enum
| Enum | Giá trị |
|---|---|
| `user_role` | `admin`, `lead`, `recruiter` |
| `hiring_unit_kind` | `client`, `department` |
| `job_status` | `draft`, `open`, `on_hold`, `closed` |
| `application_stage` | `new`, `screening`, `submitted`, `interview`, `offer`, `hired`, `rejected`, `withdrawn` |
| `ai_level` | `high`, `medium`, `low`, `insufficient` |
| `processing_status` | `pending`, `running`, `done`, `failed` |
| `candidate_source` | `upload`, `email`, `form`, `import` |
| `extraction_method` | `pdf_text`, `docx`, `ocr`, `plain` |
| `criterion_result` | `met`, `partial`, `not_met`, `unknown` |
| `email_status` | `draft`, `queued`, `sent`, `failed`, `cancelled` |
| `task_status` | `todo`, `doing`, `done`, `cancelled` |
| `activity_type` | `note`, `call`, `email_sent`, `stage_changed`, `cv_uploaded`, `ai_scored`, `ai_feedback`, `interview_scheduled`, `offer_made`, `task_done` |

### Stage pipeline (tên hiển thị)
| Mã | Hiển thị | Ý nghĩa |
|---|---|---|
| `new` | Mới nhận | CV vừa vào Job, AI có thể đang chấm |
| `screening` | Đang sàng lọc | Recruiter đang xem / gọi |
| `submitted` | Đã gửi {HIRING_UNIT_LABEL} | Gửi CV cho client/trưởng bộ phận |
| `interview` | Phỏng vấn | Đã đặt ít nhất một buổi PV |
| `offer` | Offer | Đã gửi offer |
| `hired` | Nhận việc | Tạo `placements` |
| `rejected` | Không phù hợp | Có `rejected_reason` |
| `withdrawn` | Ứng viên rút | |

Chuyển stage hợp lệ: từ bất kỳ stage "mở" (`new`→`offer`) sang stage kế tiếp, lùi lại một bước, hoặc sang `rejected`/`withdrawn`. Từ `hired`/`rejected`/`withdrawn` chỉ được "khôi phục" về stage trước đó (hoàn tác). Logic đặt trong `services/pipeline.py`, có test cho mọi cặp chuyển.

T19: `offer` → `hired` là bước kế tiếp; cùng stage/nhảy bước không hợp lệ.
Move và undo cập nhật stage_entered_at ở thời điểm thao tác, ghi StageEvent mới
và activity stage_changed cùng transaction dưới row lock Application. Undo chỉ
event đổi gần nhất trong 24 giờ, đúng actor hoặc admin/lead, mỗi lần đổi một lần;
event undo không bị undo tiếp. Từ stage kết thúc chỉ đi qua API undo, không move.
Không sửa/xoá event cũ; activity metadata stage_event_id/undo_of liên kết hai event
mà không cần thêm cột. Event khởi tạo from_stage=null không thể undo. Lý do từ
chối dùng sáu giá trị chuẩn tại contract T19 spec 03; undo về bước mở xoá lý do.
Các bảng interview/offer/placement và nghiệp vụ tương ứng vẫn thuộc T21.

## Bảng
### users
`email (unique, lowercase)`, `full_name`, `role user_role`, `password_hash` (argon2), `is_active bool`, `last_login_at`.

Chi tiết kỹ thuật T04: `failed_login_attempts int default 0` (không âm), `locked_until timestamptz null`, `auth_version int default 0` (không âm). `auth_version` dùng thu hồi cả access/refresh khi đăng nhập mới, refresh, logout, đổi mật khẩu, khoá sau 5 lần sai hoặc đổi role/is_active. Không có bảng session riêng; mỗi tài khoản có một phiên hoạt động. `email` unique và có CHECK lowercase; trường public không chứa hash hoặc trạng thái bảo mật nội bộ.

### hiring_units
`name`, `kind hiring_unit_kind`, `contact_name`, `contact_email`, `notes`, `is_active`.

### jobs
`hiring_unit_id fk`, `title`, `description text`, `must_have jsonb` (mảng chuỗi), `nice_to_have jsonb` (mảng chuỗi), `location`, `employment_type`, `salary_min int null`, `salary_max int null`, `headcount int default 1`, `deadline date null`, `status job_status`, `owner_id fk users`, `opened_at`, `closed_at`, `embedding vector(EMBEDDING_DIM) null`.

### job_members
`job_id`, `user_id`, unique(job_id, user_id).

### candidates
`full_name`, `email (lowercase, index)`, `phone (chuẩn hoá E.164 nếu được, index)`, `location`, `current_title`, `years_experience numeric null`, `skills jsonb` (mảng chuỗi), `languages jsonb`, `education jsonb`, `experiences jsonb`, `source candidate_source`, `consent_at timestamptz null`, `consent_note`, `retention_until date`, `anonymized_text text`, `embedding vector(EMBEDDING_DIM) null`, `search_tsv tsvector` (trigger, cấu hình `simple` + bỏ dấu bằng `unaccent`), `merged_into_id fk candidates null`, `deleted_at`.
Index: GIN trên `search_tsv`, HNSW/IVFFlat trên `embedding` (cosine).

T05 dùng trigger BEFORE INSERT OR UPDATE (kể cả sửa trực tiếp search_tsv), ghép full_name/current_title/các phần tử skills rồi `to_tsvector('simple', public.unaccent(...))`; không gắn IMMUTABLE giả cho `unaccent`. Truy vấn chuẩn: `search_tsv @@ plainto_tsquery('simple', unaccent(:query))`, lọc `deleted_at IS NULL`. Index vector là HNSW `vector_cosine_ops`; truy vấn sắp xếp bằng khoảng cách cosine `<=>` và LIMIT. Cả Job và ứng viên lấy dimension từ `EMBEDDING_DIM` khi tạo schema; đổi cấu hình sau đó phải có migration mới và tạo lại embedding, không tự đổi schema.

### cv_files
`candidate_id fk null` (null khi chưa parse xong), `storage_key`, `original_filename`, `mime_type`, `size_bytes`, `sha256 (unique)`, `source candidate_source default upload` (T24), `extracted_text text`, `extraction_method`, `page_count`, `parsed_json jsonb`, `status processing_status`, `error text`, `parse_model`, `parse_prompt_version`, `uploaded_by fk users null`, `job_id fk null` (Job được chọn lúc upload/nhận mail, nếu có), `deleted_at`.

### applications
`candidate_id fk`, `job_id fk`, unique(candidate_id, job_id) khi `deleted_at is null`, `stage application_stage`, `stage_entered_at`, `owner_id fk users`, `rejected_reason text null`,
`ai_status processing_status`, `ai_level ai_level null`, `ai_score int null` (0–100), `ai_criteria jsonb` (xem `04`), `ai_reasons jsonb` (2–3 chuỗi), `ai_flags jsonb`, `ai_model`, `ai_prompt_version`, `ai_scored_at`, `deleted_at`.

### stage_events
`application_id`, `from_stage null`, `to_stage`, `actor_id`, `note`, `occurred_at`. Ghi mỗi lần đổi stage (kể cả hoàn tác). Nguồn chính cho báo cáo chuyển đổi và time-to-fill.

### ai_feedback
`application_id`, `user_id`, `verdict` (`agree` | `disagree`), `corrected_level ai_level null`, `comment`. Một user có thể sửa phản hồi của mình (upsert theo application_id + user_id).

### interviews
`application_id`, `round int`, `scheduled_at timestamptz`, `duration_minutes`, `location_or_link`, `interviewers jsonb` (mảng tên/email), `result` (`pending` | `pass` | `fail` | `no_show`), `feedback text`.

### offers
`application_id`, `salary int null`, `start_date date null`, `sent_at`, `status` (`draft` | `sent` | `accepted` | `declined`), `notes`.

### placements
`application_id unique`, `start_date`, `fee_amount int null`, `guarantee_until date null`, `status` (`active` | `left_in_guarantee` | `completed`).

### Chi tiết triển khai T21

Migration `0005_recruitment_records` thêm đúng ba bảng trên với RecordMixin và
deleted_at; FK application NO ACTION. Không thêm enum PostgreSQL: trạng thái
dùng VARCHAR + CHECK. Interview round > 0, duration 1–1440 phút, interviewers
JSONB mảng chuỗi (tên hoặc email do HR nhập); mặc định result=pending, mảng rỗng.
Offer mặc định draft, salary không âm; draft có sent_at=null, trạng thái đã gửi/
đồng ý/từ chối phải có sent_at. Placement mặc định active, phí không âm, ngày
bảo hành không trước ngày bắt đầu. UNIQUE application_id áp dụng cả bản đã ẩn.
Index interviews(application_id), interviews(scheduled_at), offers(application_id)
phục vụ drawer và khoảng lịch; unique placement phục vụ tra cứu theo hồ sơ.

Các mutation khoá Application rồi đọc lại record, ghi cùng transaction với
pipeline.move(commit=False), StageEvent và activity. Đặt lịch ở submitted →
interview; nếu đã interview thì không thêm stage event. Offer chuyển sang sent
ở interview → offer; placement ở offer → hired. Hồ sơ đã ở bước đích cho phép
bổ sung bản ghi mà không đổi stage. Bước khác trả 409, không nhảy qua các bước.
Kết quả phỏng vấn và accepted/declined không tự đổi stage. Undo T19 chỉ đổi
stage, giữ bản ghi nghiệp vụ để HR sửa; không xoá hoặc gửi email.

Rollout: `uv run alembic upgrade head` trước khi khởi động phiên bản mới. Đây là
migration thêm bảng, không backfill hoặc sửa dữ liệu cũ. Rollback schema chỉ sau
khi dừng phiên bản mới và backup ba bảng; downgrade xoá ba bảng nên không chạy
trên DB có dữ liệu cần giữ. Test rollback chỉ dùng DB tạm do fixture tạo.
Giới hạn tải/hiệu năng production: NOT TESTED, chưa có quy mô được phê duyệt.

### activities
`actor_id null` (null = hệ thống), `type activity_type`, `job_id null`, `application_id null`, `candidate_id null`, `payload jsonb` (không chứa nội dung CV), `occurred_at`.

`services/activity.py:log_activity(session, ...)` thêm và flush bản ghi, không commit; caller phải kiểm quyền trước và commit/rollback chung với thao tác nghiệp vụ. Payload là metadata JSON; helper từ chối khoá nhạy cảm/CV/parsed_json và giá trị bị bộ lọc PII nhận diện, không đưa input vào thông báo lỗi hay log. Caller không được đưa nội dung CV vào trường tự do. Note nghiệp vụ phải tuân thủ cùng giới hạn dữ liệu cá nhân. `occurred_at` mặc định now, cho phép caller truyền thời điểm sự kiện; actor null dành cho hệ thống.

T19 sửa false positive khi đoạn số trong UUID khớp mẫu SĐT: chỉ tham chiếu
UUID v4 dạng canonical ở khoá `*_id`/`undo_of` được nhận diện là ID trước khi
kiểm PII giá trị. Khoá nhạy cảm, giá trị không đúng UUID và mọi trường tự do
vẫn bị kiểm như trước; không đổi bộ lọc log ứng dụng hoặc lưu nội dung CV.

T15: ghi chú HR chủ động nhập qua endpoint `/applications/{id}/notes` là
activity `note` với payload `{text}`; service kiểm quyền Job trước khi lưu vào
DB nghiệp vụ. Nội dung này được giữ trong lịch sử hồ sơ có quyền, không ghi vào
log ứng dụng và không dùng để sao chép CV tự động. Service tạo note riêng,
không nới bộ lọc metadata `log_activity` của các sự kiện tự động. Activity
`ai_feedback` chỉ lưu verdict/corrected_level; comment lưu tại ai_feedback,
upsert cùng transaction với activity. Contract chi tiết tại spec 03/T15.

### tasks
`title`, `description`, `assignee_id`, `created_by`, `job_id null`, `application_id null`, `due_at null`, `status task_status`, `completed_at`.

T25: revision `0008_tasks` thêm đúng bảng này với RecordMixin/deleted_at và enum
task_status. Title VARCHAR(200) bắt buộc không trắng, description TEXT nullable;
assignee_id/created_by FK users bắt buộc, FK không cascade. Application có mặt
thì job_id bắt buộc; service suy ra Job từ Application và kiểm khớp nếu gửi cả
hai. Status mặc định todo; CHECK completed_at có giá trị khi và chỉ khi done.
Index (assignee_id,status,due_at) cho danh sách/nhắc hạn và index created_by,
job_id,application_id cho tra liên kết. Không có DELETE từ giao diện/API.
Loại việc tự động nhận diện bằng hai title cố định theo spec 06 + application_id;
không thêm cột loại/nguồn ngoài schema. Khoá transaction chung giữa tạo tay và
generator chống tạo trùng task mở trong hai lượt generator đồng thời.

Rollout: migrate trước API/worker/Beat mới; chỉ thêm bảng/enum, không backfill.
Downgrade xoá bảng/enum, chỉ chạy trên DB tạm trong test; môi trường có dữ liệu
cần dừng writer và backup trước rollback. Tải/thời gian migration production:
NOT TESTED, chưa có quy mô được duyệt.

### email_templates
`key unique` (vd. `cv_received`, `interview_invite`, `rejection`, `offer`), `name`, `stage application_stage null`, `subject` (Jinja2), `body` (Jinja2, Markdown đơn giản → HTML), `is_active`, `requires_confirmation bool default true`.

### email_messages
`application_id null`, `template_id null`, `to_email`, `cc jsonb`, `subject`, `body_html`, `status email_status`, `scheduled_for null`, `sent_at`, `error`, `created_by`, `message_id` (header SMTP).

T23 dùng các cột có sẵn, không migration mới: tạo nháp ghi created_by là tác giả;
khi xác nhận send/gửi lại cập nhật thành người xác nhận để worker kiểm quyền
và ghi actor của email_sent. scheduled_for là mốc hẹn/checkpoint delivery,
failed có mốc này nghĩa là còn retry, null nghĩa là đã hết hoặc không hẹn.
message_id là ID lượt xác nhận/header SMTP, giữ nguyên qua retry, đổi khi HR
bấm gửi lại. Chi tiết API/vòng đời/giới hạn SMTP tại spec 03/06.

### Chi tiết triển khai T22

Migration `0006_email_templates` thêm hai bảng trên và enum `email_status`.
Template có RecordMixin, key unique tối đa 64 ký tự, name 200, subject 500,
body text; stage dùng enum hiện có và nullable. Mặc định is_active=true,
requires_confirmation=true; CHECK chỉ key=cv_received được phép có
requires_confirmation=false. Key không đổi qua API; ngừng sử dụng bằng
is_active=false, không xoá cứng. Mẫu không có dữ liệu ứng viên nên không thêm
deleted_at; email_messages có deleted_at, cc mặc định [], CHECK JSONB array,
status mặc định draft. Các FK không cascade; index application_id/template_id/
created_by phục vụ lịch sử và lookup. Không mở endpoint ghi/gửi message ở T22.

Migration seed năm mẫu với nội dung tiếng Việt được đóng băng trong revision;
seed_catalog cũng thêm mẫu còn thiếu theo key (ON CONFLICT DO NOTHING), giữ
nguyên mọi sửa đổi hoặc trạng thái ngừng sử dụng của HR. Chỉ cv_received mặc
định không cần xác nhận; thông báo xử lý dữ liệu không tự sinh consent.

Rollout: chạy `uv run alembic upgrade head` trước phiên bản mới; chỉ thêm bảng,
không thay đổi dữ liệu nghiệp vụ cũ. Rollback chỉ sau khi dừng writer và backup
hai bảng; downgrade xoá hai bảng/enum email_status và chỉ được kiểm trên DB tạm.
Thời gian migration và tải production: NOT TESTED, chưa có quy mô được duyệt.

### inbound_emails
`message_id unique`, `from_email`, `subject`, `received_at`, `attachment_count`, `processed_at`, `status`, `error`. Không lưu thân mail.

T24: migration `0007_inbound_emails` thêm bảng này (RecordMixin + deleted_at)
và `cv_files.source` NOT NULL, dùng enum candidate_source hiện có/default upload;
không thay nguồn của Candidate cũ. File email có source=email, uploaded_by=null;
Candidate mới nhận nguồn từ file, bản khớp liên hệ giữ nguồn ban đầu.
Inbound status VARCHAR/CHECK processed hoặc ignored, attachment_count >= 0;
from_email tối đa 254, subject lưu tối đa 2000; error chỉ thông báo cố định.
received_at lấy Date (thiếu/sai dùng thời điểm đọc), processed_at là lúc tiếp nhận
tệp, không phải lúc AI xong. Không lưu body. UNIQUE message_id và advisory lock
chống đọc đồng thời; SHA-256 unique dùng chung upload, kể cả bản đã ẩn.
Không có cột/FK mới khác: EmailMessage tự động dùng cùng UUID của CvFile, một
receipt/file, application_id có thể null khi chưa xác định Job. created_by là
owner Job, hoặc admin đang hoạt động đầu tiên theo UUID khi không có Job;
activity email_sent có actor null vì đây là thao tác hệ thống.

Rollout: migrate trước khi chạy API/worker/Beat mới. Default upload tương thích
file cũ, không rewrite CV hoặc backfill PII. Rollback sau khi dừng writer/Beat
và backup inbound_emails; downgrade xoá bảng và cột nguồn nên chỉ kiểm trên DB
tạm. Thời gian/tải production: NOT TESTED, chưa có quy mô được phê duyệt.

### audit_log
`actor_id`, `action` (vd. `candidate.view`, `candidate.export`, `candidate.purge`, `user.role_change`), `entity`, `entity_id`, `occurred_at`, `ip`. Chỉ ghi id, không ghi nội dung.
`details jsonb not null default '{}'` (thêm ở T17): chỉ số đếm và định danh, ví dụ `{"record_count": 12, "job_id": "…"}`. Không ghi họ tên, email, SĐT, nội dung CV hay giá trị bộ lọc dạng chữ.

### data_requests
`candidate_id`, `kind` (`delete` | `export`), `requested_by_note`, `status` (`open` | `done` | `rejected`), `handled_by`, `handled_at`.

T29 revision `0009_data_privacy`: thêm bảng này với RecordMixin (UUID,
created_at/updated_at), FK candidate/handled_by, index candidate_id, CHECK kind,
status và handled: open chưa có handled_at/handled_by, kết thúc bắt buộc handled_at.
handled_by nullable cho job hệ thống. Không thêm DELETE bản ghi lịch sử.

Candidate thêm expired_at/purge_pending_at/purged_at timestamptz nullable và
index retention_until cho lịch hằng ngày. Cho phép SQL NULL ở tên/các mảng dữ
liệu cá nhân/search_tsv; trigger đặt search_tsv NULL khi purge_pending_at có giá
trị, vẫn dựng full-text như trước cho hồ sơ hoạt động. CV storage_key/filename/
sha256, Application ai_criteria/reasons/flags, email to/cc/subject/body,
inbound message_id/from/subject, Task title, Interview interviewers nullable
để xoá nội dung. Các service tạo/sửa bình thường giữ validation cũ, DTO hồ sơ
hoạt động giữ contract cũ; purge DTO không được trả qua những API hồ sơ đó.
AuditLog.actor_id nullable như ghi chú review T05; NULL là hệ thống, không tạo
user giả để làm actor. Consent/note/raw JSON được đặt SQL NULL (không JSON null).

Rollout: migrate trước khi restart API/worker và bật Beat. Migration không xoá
dữ liệu hiện hữu; chạy Beat mới thực thi chính sách. Rollback schema chỉ trước
khi có yêu cầu/actor hệ thống/purge_pending; downgrade có guard từ chối nếu đã
phát sinh dữ liệu này, không dựng lại PII hay xoá audit để làm migration pass.
Sau khi đã xử lý phải dùng forward migration; không thể hoàn tác purge bằng
downgrade. Kiểm upgrade/downgrade/upgrade chỉ trên DB tạm; thời gian khóa ở quy
mô production và quy trình xoá backup: NOT TESTED.

### erased_contacts
T29 revision `0010_erased_contacts`: RecordMixin, `contact_hash` varchar(64)
(index), `frozen_at` timestamptz. Mỗi dòng là HMAC-SHA256 (khoá SECRET_KEY) của
một email/SĐT đã chuẩn hoá của người vừa bị freeze; không lưu liên hệ dạng đọc
được, không FK tới Candidate. Chỉ dùng để nhận ra CV đã nhận trước lúc xoá nhưng
còn trong hàng đợi (chưa có candidate_id). Job hằng ngày xoá marker khi không còn
CvFile pending/running chưa gắn hồ sơ có created_at ≤ frozen_at.

## Seed dev
Lệnh seed tạo: 1 admin, 1 lead, 2 recruiter (mật khẩu chỉ cho dev), 3 đơn vị tuyển, 5 Job, ~40 ứng viên giả từ `data/sample_cvs/`, applications ở nhiều stage, vài interview/offer/placement, task và email mẫu.

T18 triển khai phần M1 bằng `uv run python -m app.scripts.seed`: 4 tài khoản
giả, 3 đơn vị, 5 Job, 40 CV kỹ thuật số qua pipeline thật với fake provider và
lịch sử stage giả. Chạy lại không tạo trùng hoặc ghi đè kết quả/chỉnh sửa HR;
không tạo bằng chứng đồng ý giả. Interview/offer/placement/task/email mẫu được
bổ sung ở task sở hữu bảng T21–T23/T25 (câu hỏi #66), không thêm schema tại T18.
T21 bổ sung initial stage hired và 5 interview/10 offer/5 placement giả cho
seed mới, cùng initial StageEvent. Chỉ tạo trong lúc khởi tạo lịch sử lần đầu;
không thêm ngược hoặc ghi đè các hồ sơ có lịch sử/chỉnh sửa HR từ trước.
