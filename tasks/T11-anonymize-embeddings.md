# T11 · Ẩn danh và embedding
Mốc: M1 · Phụ thuộc: T10 · Spec: `04` bước 5–6, Tìm kiếm

## Việc cần làm
- `app/ai/anonymize.py` theo spec; tích hợp vào pipeline sau parse, lưu `anonymized_text`.
- `app/ai/embed.py`: `FakeEmbedder` (hash tất định, đúng `EMBEDDING_DIM`), `LocalEmbedder` (sentence-transformers, tải model lần đầu, cache ở `var/models`); factory theo `EMBEDDING_PROVIDER`.
- Embedding ứng viên trong pipeline; embedding Job khi tạo/sửa Job (hook dùng ở T13).
- Lệnh `uv run python -m app.scripts.reembed --all` để tính lại khi đổi model.

## Tiêu chí nghiệm thu
- Test ẩn danh trên ≥ 15 CV mẫu: `anonymized_text` không chứa họ tên (có dấu và không dấu), email, SĐT, ngày sinh, từ chỉ giới tính.
- Test pipeline: ứng viên có embedding đúng số chiều; tìm top-k với FakeEmbedder chạy được.
