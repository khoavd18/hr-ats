# 04 · AI pipeline

Toàn bộ code AI nằm trong `backend/app/ai/`. Prompt nằm trong `prompts/<task>/v<N>.md`, có version; mỗi kết quả lưu `model` và `prompt_version`.

## Luồng tổng
```
upload / email ──► cv_files(pending)
   process_cv_file:
     1. extract_text          (local)
     2. pre_redact            (local: che email, SĐT trước khi gửi đi)
     3. parse_cv              (LLM)  ──► candidates + parsed_json
     4. dedupe                (local)
     5. anonymize             (local) ──► candidates.anonymized_text
     6. embed                 (embedding) ──► candidates.embedding
     7. nếu có job_id: tạo application ──► score_application
   score_application:
     8. judge_criteria        (LLM, chỉ dùng anonymized_text + yêu cầu Job)
     9. compute_score         (local, tất định)
```
Mỗi bước bọc try/except, ghi `status/error` lên bản ghi, không làm hỏng bước khác. Lỗi ở một file không chặn các file còn lại trong cùng lần upload.

## 1. Trích text (`ai/extract.py`)
- PDF: PyMuPDF lấy text theo block, sắp theo cột (trái → phải, trên → dưới) để CV hai cột không bị trộn dòng.
- Trang có < 50 ký tự text → render 300 DPI → Tesseract (`TESSERACT_LANGS`). `extraction_method = ocr` nếu có ít nhất một trang OCR.
- DOCX: python-docx, gồm cả bảng. Ảnh JPG/PNG: OCR.
- Chuẩn hoá Unicode NFC (quan trọng với tiếng Việt), gộp khoảng trắng, giữ xuống dòng.
- Text rỗng sau khi trích → `failed` với lỗi tiếng Việt "Không đọc được nội dung CV".

## 2. Che trước khi gửi (`ai/redact.py`)
- Tìm email (regex) và số điện thoại Việt Nam/quốc tế (regex cho `0xxxxxxxxx`, `+84`, có dấu cách/chấm/gạch), lưu giá trị gốc vào biến cục bộ, thay trong text bằng `[EMAIL]`, `[PHONE]`.
- Giá trị gốc được ghi thẳng vào `candidates.email/phone`, không bao giờ gửi cho LLM.

## 3. Parse CV (`ai/parse.py`, prompt `prompts/parse_cv/v1.md`)
Gửi text đã che ở bước 2. Tách thành 3 lời gọi song song (theo paper Layout-Aware, xem `docs/research/papers.md`):
- `basic`: họ tên, vị trí hiện tại, địa điểm, số năm kinh nghiệm, ngôn ngữ
- `experience`: danh sách kinh nghiệm `{company, title, start, end, description}` và học vấn `{school, degree, major, start, end}`
- `skills`: danh sách kỹ năng đã chuẩn hoá (chữ thường, gộp đồng nghĩa phổ biến)

Mỗi lời gọi trả JSON theo schema Pydantic trong `ai/schemas.py`; validate, nếu sai thì gọi lại một lần kèm thông báo lỗi validate; vẫn sai thì `failed`. Ngày tháng dạng `YYYY-MM` hoặc `null`; không bịa thông tin không có trong CV (prompt yêu cầu trả `null`).

## 4. Chống trùng (`services/dedupe.py`)
- Khớp tuyệt đối: cùng email hoặc cùng phone chuẩn hoá → gắn file vào ứng viên cũ, cập nhật thông tin mới nhất.
- Không có email/phone: cosine embedding > 0.95 **và** tên chuẩn hoá (bỏ dấu, chữ thường) trùng → đánh dấu "có thể trùng" để người dùng gộp, không tự gộp.
- Cùng `sha256` file → không xử lý lại, trả về bản ghi cũ.

## 5. Ẩn danh (`ai/anonymize.py`)
Tạo `anonymized_text` từ text đã che: thay họ tên (cả dạng có dấu, không dấu, viết hoa) bằng `[TÊN]`; xoá dòng ngày sinh/tuổi, giới tính ("Nam", "Nữ", "Giới tính"), tình trạng hôn nhân, địa chỉ nhà, link mạng xã hội cá nhân. Có test với ít nhất 15 mẫu CV giả.
**Chỉ `anonymized_text` được dùng cho embedding và chấm điểm.**

## 6. Embedding (`ai/embed.py`)
Interface `Embedder.embed(texts) -> list[list[float]]`; bản `LocalEmbedder` (sentence-transformers, chuẩn hoá L2) và `FakeEmbedder` (hash tất định, cho test). Embedding cho Job lấy từ `title + description + must_have + nice_to_have`.

## 8. Chấm theo tiêu chí (`ai/score.py`, prompt `prompts/score_cv/v1.md`)
Đầu vào: `anonymized_text`, danh sách `must_have`, `nice_to_have`, tiêu đề và mô tả Job.
LLM trả cho **từng tiêu chí**:
```json
{"criterion": "3 năm kinh nghiệm Java", "kind": "must", "result": "met|partial|not_met|unknown",
 "evidence": "trích ngắn ≤ 20 từ từ CV hoặc null"}
```
cùng `reasons` (2–3 câu tiếng Việt, ngắn, không nhắc tên/giới tính/tuổi) và `flags` (mảng mã: `job_hopping`, `employment_gap`, `missing_must_have`, `overqualified`, `unclear_cv`).
`evidence` phải là chuỗi có thật trong `anonymized_text` (code kiểm tra; nếu không khớp thì đặt `result = unknown`).

## 9. Tính điểm tất định (`ai/scoring_rules.py`)
- Giá trị: `met = 1`, `partial = 0.5`, `not_met = 0`, `unknown = 0`.
- `must_score` = trung bình tiêu chí must; `nice_score` = trung bình tiêu chí nice (nếu không có nice thì bằng `must_score`).
- `ai_score = round(100 * (0.75 * must_score + 0.25 * nice_score))`.
- `ai_level`:
  - `insufficient` nếu ≥ 50% tiêu chí là `unknown` hoặc CV quá ngắn (< 300 ký tự);
  - `low` nếu có tiêu chí must `not_met`;
  - `high` nếu `ai_score ≥ 75` và không có must `not_met`;
  - còn lại `medium`.
Ngưỡng là hằng số cấu hình được; có unit test bao phủ mọi nhánh.

## LLM adapter (`ai/llm.py`)
```python
class LLMClient(Protocol):
    def complete_json(self, *, system: str, user: str, schema: type[BaseModel],
                      temperature: float = 0) -> BaseModel: ...
```
Bản: `FakeLLM` (đọc fixture theo hash input, hoặc sinh kết quả tất định từ từ khoá — đủ để test end-to-end), `AnthropicLLM`, `OpenAILLM`, `OllamaLLM`. Timeout 60 giây, retry 2 lần với backoff khi lỗi mạng/429. Ghi log: model, số token, thời gian, **không ghi nội dung**.

## Tìm kiếm
- Full-text: `search_tsv` (unaccent) cho tên, kỹ năng, chức danh.
- Theo nghĩa: embedding câu truy vấn → top-k cosine trên `candidates.embedding`.
- Gợi ý cho Job: top-50 ứng viên gần `jobs.embedding`, loại người đã có application, chỉ những ai còn trong hạn lưu trữ.

## Đánh giá (`eval/`)
- `eval/generate_synthetic_cvs.py`: sinh CV giả tiếng Việt (DOCX + PDF, 1 cột, 2 cột, có bảng, bản ảnh scan có nhiễu) cùng file nhãn JSON (thông tin đúng + mức phù hợp với vài Job mẫu).
- `eval/run_parse_eval.py`: độ chính xác theo trường (exact match cho email/phone/tên; F1 cho kỹ năng).
- `eval/run_score_eval.py`: so `ai_level` với nhãn; precision@10, mức đồng thuận (Cohen's kappa); chạy được trên bộ công khai (xem `docs/research/datasets.md`) và trên bộ CV nội bộ đã ẩn danh đặt ngoài repo (`EVAL_DATA_DIR`).
- `eval/run_bias_check.py`: cùng một CV, thay tên nam/nữ và các tên vùng miền khác nhau → mức chênh `ai_score`; báo cáo nếu chênh > 5 điểm.
- Kết quả ghi `eval/reports/<ngày>-<model>-<prompt_version>.md`. Đổi model hoặc prompt phải chạy lại.
