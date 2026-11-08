# 02 · Mô hình dữ liệu

Mọi bảng có `id uuid pk`, `created_at timestamptz default now()`, `updated_at timestamptz`. Bảng có dữ liệu ứng viên có thêm `deleted_at timestamptz null` (soft delete). Tên bảng/cột tiếng Anh, snake_case.

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

## Bảng
### users
`email (unique, lowercase)`, `full_name`, `role user_role`, `password_hash` (argon2), `is_active bool`, `last_login_at`.

### hiring_units
`name`, `kind hiring_unit_kind`, `contact_name`, `contact_email`, `notes`, `is_active`.

### jobs
`hiring_unit_id fk`, `title`, `description text`, `must_have jsonb` (mảng chuỗi), `nice_to_have jsonb` (mảng chuỗi), `location`, `employment_type`, `salary_min int null`, `salary_max int null`, `headcount int default 1`, `deadline date null`, `status job_status`, `owner_id fk users`, `opened_at`, `closed_at`, `embedding vector(EMBEDDING_DIM) null`.

### job_members
`job_id`, `user_id`, unique(job_id, user_id).

### candidates
`full_name`, `email (lowercase, index)`, `phone (chuẩn hoá E.164 nếu được, index)`, `location`, `current_title`, `years_experience numeric null`, `skills jsonb`, `languages jsonb`, `education jsonb`, `experiences jsonb`, `source candidate_source`, `consent_at timestamptz null`, `consent_note`, `retention_until date`, `anonymized_text text`, `embedding vector(EMBEDDING_DIM) null`, `search_tsv tsvector` (generated, cấu hình `simple` + bỏ dấu bằng `unaccent`), `merged_into_id fk candidates null`, `deleted_at`.
Index: GIN trên `search_tsv`, HNSW/IVFFlat trên `embedding` (cosine).

### cv_files
`candidate_id fk null` (null khi chưa parse xong), `storage_key`, `original_filename`, `mime_type`, `size_bytes`, `sha256 (unique)`, `extracted_text text`, `extraction_method`, `page_count`, `parsed_json jsonb`, `status processing_status`, `error text`, `parse_model`, `parse_prompt_version`, `uploaded_by fk users null`, `job_id fk null` (Job được chọn lúc upload, nếu có), `deleted_at`.

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

### activities
`actor_id null` (null = hệ thống), `type activity_type`, `job_id null`, `application_id null`, `candidate_id null`, `payload jsonb` (không chứa nội dung CV), `occurred_at`.

### tasks
`title`, `description`, `assignee_id`, `created_by`, `job_id null`, `application_id null`, `due_at null`, `status task_status`, `completed_at`.

### email_templates
`key unique` (vd. `cv_received`, `interview_invite`, `rejection`, `offer`), `name`, `stage application_stage null`, `subject` (Jinja2), `body` (Jinja2, Markdown đơn giản → HTML), `is_active`, `requires_confirmation bool default true`.

### email_messages
`application_id null`, `template_id null`, `to_email`, `cc jsonb`, `subject`, `body_html`, `status email_status`, `scheduled_for null`, `sent_at`, `error`, `created_by`, `message_id` (header SMTP).

### inbound_emails
`message_id unique`, `from_email`, `subject`, `received_at`, `attachment_count`, `processed_at`, `status`, `error`. Không lưu thân mail.

### audit_log
`actor_id`, `action` (vd. `candidate.view`, `candidate.export`, `candidate.purge`, `user.role_change`), `entity`, `entity_id`, `occurred_at`, `ip`. Chỉ ghi id, không ghi nội dung.

### data_requests
`candidate_id`, `kind` (`delete` | `export`), `requested_by_note`, `status` (`open` | `done` | `rejected`), `handled_by`, `handled_at`.

## Seed dev
Lệnh seed tạo: 1 admin, 1 lead, 2 recruiter (mật khẩu chỉ cho dev), 3 đơn vị tuyển, 5 Job, ~40 ứng viên giả từ `data/sample_cvs/`, applications ở nhiều stage, vài interview/offer/placement, task và email mẫu.
