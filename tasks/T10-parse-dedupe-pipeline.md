# T10 · Parse CV, chống trùng, pipeline xử lý
Mốc: M1 · Phụ thuộc: T07, T08, T09 · Spec: `04` bước 3–4, Luồng tổng

## Việc cần làm
- `app/ai/parse.py`: gọi 3 phần parse song song (ThreadPoolExecutor), gộp thành `ParsedCV`.
- `app/services/dedupe.py` theo spec (email/SĐT khớp → gắn ứng viên cũ; sha256 trùng → bỏ qua; nghi trùng → đánh dấu `possible_duplicate_of` trong `parsed_json`).
- Hoàn thiện worker `process_cv_file(cv_file_id)`: trích text → redact → parse → tạo/cập nhật `candidates` → (bước 5–7 để T11/T12, gọi hook rỗng) → `status=done`; lỗi bước nào ghi `error` tiếng Việt, `status=failed`. Idempotent.
- `candidates.retention_until` = hôm nay + `DATA_RETENTION_MONTHS`.

## Tiêu chí nghiệm thu
- Test end-to-end với FakeLLM: upload 10 CV mẫu → 10 ứng viên với email/SĐT đúng theo nhãn; upload lại một CV khác định dạng cùng email → không tạo ứng viên mới; một file hỏng → chỉ file đó `failed`.
