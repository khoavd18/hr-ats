# T05 · Mô hình dữ liệu lõi
Mốc: M1 · Phụ thuộc: T04 · Spec: `02-data-model.md`

## Việc cần làm
- Enum và model + migration cho: `hiring_units`, `jobs`, `job_members`, `candidates`, `cv_files`, `applications`, `stage_events`, `activities`, `ai_feedback`, `audit_log`. Cột vector dùng `EMBEDDING_DIM`.
- `candidates.search_tsv`: cột generated hoặc trigger dùng `unaccent` + cấu hình `simple` trên họ tên, chức danh, kỹ năng; index GIN. Index vector cosine (HNSW).
- Unique có điều kiện cho `applications(candidate_id, job_id) where deleted_at is null`.
- Pydantic schemas cơ bản cho các bảng (đọc).
- Hoàn thiện `authorize()` cho Job và ứng viên dựa trên owner/member.
- `app/services/activity.py`: hàm `log_activity(...)` dùng chung.

## Tiêu chí nghiệm thu
- `alembic upgrade head` và `downgrade base` chạy được.
- Test: tạo bản ghi mỗi bảng; unique application; tìm full-text không dấu ("nguyen" khớp "Nguyễn"); truy vấn vector top-k chạy; bảng quyền recruiter với Job không phải của mình bị từ chối.

## Ghi chú từ review T02
- Bổ sung vào `backend/app/core/logging.py` các khoá nhạy cảm cho dữ liệu ứng viên: `full_name`, `name`, `candidate_name`, `address`, `phone_number`, `date_of_birth` (khớp chính xác và hậu tố), kèm test; cập nhật spec 07.
