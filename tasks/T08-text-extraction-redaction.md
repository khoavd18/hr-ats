# T08 · Trích text và che thông tin liên hệ
Mốc: M1 · Phụ thuộc: T02, T06 · Spec: `04-ai-pipeline.md` bước 1–2

## Việc cần làm
- `app/ai/extract.py`: `extract_text(data: bytes, mime: str) -> ExtractResult(text, method, page_count)` theo spec (sắp block theo cột, OCR trang ít chữ, DOCX gồm bảng, chuẩn hoá NFC).
- Tesseract là dependency hệ thống: ghi hướng dẫn cài (Windows: UB Mannheim installer + gói `vie`; Docker: `apt-get install tesseract-ocr tesseract-ocr-vie`) vào README; nếu thiếu Tesseract và `OCR_ENABLED=true` → lỗi rõ ràng "Máy chủ chưa cài OCR", không crash worker.
- `app/ai/redact.py`: `redact_contacts(text) -> (redacted_text, emails, phones)`; chuẩn hoá SĐT Việt Nam về `+84…`.

## Tiêu chí nghiệm thu
- Test trên `data/sample_cvs/`: CV 2 cột không trộn dòng giữa hai cột (kiểm bằng thứ tự các mục trong nhãn); CV DOCX có bảng lấy được kỹ năng; CV ảnh scan trích được email khi có Tesseract (test này `skip` nếu máy không có Tesseract).
- Test redact với ít nhất 12 dạng SĐT/email; text sau redact không còn chuỗi gốc.
