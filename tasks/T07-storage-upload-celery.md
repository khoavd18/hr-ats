# T07 · Lưu file, upload CV, Celery
Mốc: M1 · Phụ thuộc: T05 · Spec: `01` (Hàng đợi), `03` (CV & ứng viên: POST /cv-files, GET /cv-files/{id}, download), `07` (Upload)

## Việc cần làm
- `app/storage/`: interface `Storage` (`put(bytes, mime) -> key`, `get(key)`, `delete(key)`), `LocalStorage`, `S3Storage` (boto3), chọn theo `STORAGE_BACKEND`. Key ngẫu nhiên, không chứa tên file gốc.
- `app/workers/celery_app.py`: app Celery, 3 queue, chế độ eager khi `APP_ENV=test`.
- `POST /api/v1/cv-files`: nhiều file; kiểm magic bytes (PDF, DOCX, JPEG, PNG), ≤ 10 MB, ≤ 50 file; từ chối `.docm`/có macro; tính `sha256` — trùng thì trả bản ghi cũ; tạo `cv_files(pending)`, ghi activity `cv_uploaded`, xếp job `process_cv_file` (task rỗng tạm thời, đặt `status=done` — logic thật ở T10).
- `GET /cv-files/{id}`, `GET /cv-files/{id}/download` (kiểm quyền, ghi audit).

## Tiêu chí nghiệm thu
- Test: upload 3 file hợp lệ + 1 file `.exe` đổi đuôi `.pdf` → 3 tạo, 1 lỗi tiếng Việt; upload lại cùng file → không tạo bản ghi mới; download của recruiter không có quyền → 403; audit có bản ghi download.
