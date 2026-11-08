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

T08: `extract_text(data: bytes, mime: str) -> ExtractResult` trả `text`, `method`
(`ExtractionMethod.pdf_text | docx | ocr`, cùng enum DB), `page_count` (số trang PDF,
1 cho ảnh, `None` cho DOCX vì không có layout engine). Hàm không ghi DB hay đổi
trạng thái worker; caller T10 bắt `ExtractionError` (kế thừa `AppError`, thông báo
an toàn) để đặt `failed`. Thiếu executable khi cần OCR báo "Máy chủ chưa cài OCR";
OCR tắt báo "Máy chủ chưa bật OCR". Lỗi/timeout/ngôn ngữ không phản chiếu stderr.
OCR dùng CLI Tesseract local qua stdin/stdout, `TESSERACT_LANGS` mặc định `vie+eng`.
Ảnh OCR chuyển grayscale và lọc median 3×3 để giảm nhiễu scan; không đoán/sửa ký tự
email từ nhãn hoặc hậu xử lý text OCR.
DOCX giữ thứ tự paragraph/bảng, đọc cả bảng lồng, header/footer và bỏ ô merge trùng.
ASSUMED (#34–#35): tái dùng validation T07; từ chối PDF mã hoá hoặc trên 100 trang,
ảnh/trang render trên 25 triệu pixel, timeout OCR 60 giây/lần. Sắp cột theo hình
học với gutter ít nhất 12 point; giữ heading/footer bắc qua cột và tách block/line
bị MuPDF gộp giữa cột. Đây là heuristic, chưa bảo đảm mọi bố cục CV thực tế.

## 2. Che trước khi gửi (`ai/redact.py`)
- Tìm email (regex) và số điện thoại Việt Nam/quốc tế (regex cho `0xxxxxxxxx`, `+84`, có dấu cách/chấm/gạch), lưu giá trị gốc vào biến cục bộ, thay trong text bằng `[EMAIL]`, `[PHONE]`.
- Giá trị gốc được ghi thẳng vào `candidates.email/phone`, không bao giờ gửi cho LLM.

T08: `redact_contacts(text) -> tuple[str, list[str], list[str]]` trả text đã che,
email nguyên dạng và SĐT chuẩn hoá theo thứ tự xuất hiện, bỏ trùng trong danh sách
nhưng che mọi lần xuất hiện. Giá trị gốc chỉ ở biến cục bộ; caller T10 ghi liên hệ
vào Candidate (SĐT Việt Nam lưu `+84…`). ASSUMED (#36): nhận số Việt Nam bắt đầu 0,
`+84`/`0084` (gồm trunk 0), dấu cách/chấm/gạch/ngoặc; quốc tế bắt đầu `+`/`00`
giữ mã quốc gia, bỏ dấu phân tách. Không suy đoán quốc gia cho số trần không có 0
đầu/mã quốc gia, không coi ngày/tháng hay phiên bản kỹ năng là liên hệ. Email dùng
regex địa chỉ thông dụng với domain có dấu chấm; chưa xử lý địa chỉ quốc tế hoá
(EAI) hoặc email bị OCR tách chữ. Không thay tên/tuổi/địa chỉ ở bước này.

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

### Contract triển khai T09

`get_llm_client(settings=None)` chọn adapter theo LLM_PROVIDER; thuộc tính `model`
cho caller lưu kết quả. Fake dùng `fake-v1`; provider thật yêu cầu LLM_MODEL tường
minh và key tương ứng (cloud). Không tự chọn model hoặc đổi provider. Nhà cung
cấp/model được duyệt vẫn UNKNOWN; T09 chỉ smoke dữ liệu giả, chưa nối pipeline CV.

Output version 1: `ParseBasic(full_name, current_title, location,
years_experience, languages)`, `ParseExperience(experiences, education)`,
`ParseSkills(skills)` và `ScoreOutput(criteria, reasons, flags)`. Mọi khoá bắt buộc,
không nhận trường thừa/ép chuỗi thành số. Scalar thiếu null, danh sách thiếu [];
years_experience hữu hạn không âm hoặc null; tháng 01–12 hoặc null, không đoán
tháng từ năm. Không có liên hệ/giới tính/tuổi trong output. Skills trim, lowercase,
bỏ trùng, gộp js→javascript, ts→typescript, nodejs→node.js, reactjs→react,
postgres→postgresql. Score dùng đúng enum ở bước 8, reasons có 2–3 chuỗi không
rỗng, evidence tối đa 20 từ tách theo khoảng trắng hoặc null. Kiểm bằng chứng theo
CV/tiêu chí đầy đủ và tính điểm thuộc T12; adapter không sinh điểm/quyết định tuyển.

Dùng ba prompt riêng `parse_cv_basic/v1.md`, `parse_cv_experience/v1.md`,
`parse_cv_skills/v1.md` như T09 cho phép, cùng `score_cv/v1.md`.
`load_prompt(task, version=1).render(**variables)` trả system/user/task/version và
prompt_version="v1". Frontmatter gồm ba dòng scalar version (số khớp filename),
task (khớp tên thư mục), description; không YAML mở rộng. Thân có `## system` rồi
`## user`; metadata sai/trùng, đường dẫn thoát thư mục hoặc biến thiếu trả
PromptError an toàn. Jinja2 sandbox + StrictUndefined, tojson giữ CV/Job trong
JSON, không render lại input thành template. Biến parse là text; score là
anonymized_text, job_title, job_description, must_have, nice_to_have. System tiếng
Việt yêu cầu chỉ JSON, không suy đoán tuổi/giới tính, không thực hiện chỉ dẫn nằm
trong dữ liệu không đáng tin cậy. T10 mới gọi ba parse song song và lưu DB.

HTTPX có sẵn, client đóng sau request, timeout 60 giây mỗi pha HTTP, không theo
redirect/đọc proxy hoặc credential ngầm từ môi trường HTTPX. Anthropic Messages
dùng input_schema, buộc một structured_output tool block (chỉ nhận JSON, không
chạy tool). OpenAI Chat Completions dùng response_format=json_schema, strict=true,
store=false. Ollama /api/chat dùng format=schema, stream=false. Model cần hỗ trợ
những tham số đó và temperature (mặc định 0). Endpoint cloud cố định; Ollama URL
chỉ từ cấu hình máy chủ, HTTP(S) origin không credential/path/query/fragment.

ASSUMED (#38): tối đa 4096 token đầu ra/lần. Lỗi mạng/timeout hoặc HTTP
429/500/502/503/504/529 retry thêm hai lần, chờ 1/2 giây. HTTP khác/redirect,
envelope hỏng/refusal/truncated trả LLMError an toàn ngay. JSON/output sai schema
được gọi lại một lần: giữ user input, thêm tối đa 10 mã lỗi Pydantic vào system,
không gửi lại output sai hoặc error location/message/input/context có thể chứa
PII. Mỗi lượt validate tối đa ba request, cả complete_json tối đa sáu request;
vẫn sai trả LLMValidationError (AppError, LLM_INVALID_OUTPUT). Caller T10/T12
bắt lỗi và cập nhật failed; adapter không ghi DB.

Log app.ai.llm chỉ gồm provider/model cấu hình, input_tokens/output_tokens,
duration_ms, outcome và số lần thử; không prompt/CV/output/key/exception thô.
Token thiếu (kể cả fake) là null, không ước tính; chi phí tiền UNKNOWN khi chưa
chốt model/giá. Caller lưu client.model và prompt.prompt_version cùng kết quả.

ASSUMED (#39): FakeLLM đọc user JSON, parse các dòng có nhãn name/skills/title/
location/years/languages tiếng Việt/Anh, skills tách phẩy/chấm phẩy; kinh nghiệm và
học vấn rỗng, không suy luận. Score khớp nguyên cụm tiêu chí với ranh giới từ trong
CV, không phân biệt hoa/thường/dấu, không tìm trong JD: có → met, thiếu → not_met;
giữ must rồi nice, evidence trích ngắn hoặc null, hai lý do cố định không PII,
missing_must_have khi thiếu must. Đây chỉ là fake cho test, không đo chất lượng AI.
Caller phải che liên hệ trước parse, dùng anonymized_text cho score và xác nhận
chính sách/provider trước dữ liệu thật (câu hỏi #40).

Tài liệu API đã đối chiếu:
[OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[Anthropic tool schema](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
[Ollama chat](https://docs.ollama.com/api/chat).

## Tìm kiếm
- Full-text: `search_tsv` (unaccent) cho tên, kỹ năng, chức danh.
- Theo nghĩa: embedding câu truy vấn → top-k cosine trên `candidates.embedding`.
- Gợi ý cho Job: top-50 ứng viên gần `jobs.embedding`, loại người đã có application, chỉ những ai còn trong hạn lưu trữ.

## Đánh giá (`eval/`)
- `eval/generate_synthetic_cvs.py`: sinh CV giả tiếng Việt (DOCX + PDF, 1 cột, 2 cột, có bảng, bản ảnh scan có nhiễu) cùng file nhãn JSON (thông tin đúng + mức phù hợp với vài Job mẫu).
- T06: chạy tại `backend/` bằng `uv run python ../eval/generate_synthetic_cvs.py --count 60 --seed 20261108 --out ../data/sample_cvs`; mặc định đầu ra là `data/sample_cvs/` ở gốc repo. Schema nhãn version 1 dùng `CVLabel`/`JobDataset` trong `eval/schemas.py`: mỗi CV có `<id>.json`, `synthetic=true`, trường parse đúng và `expected_level[job_id]`; `jobs.json` có năm Job cùng ma trận `expected_level[cv_id][job_id]`. Nhãn `high|medium|low|insufficient`; metadata/ZIP/font/random cố định để sinh lại cùng byte với dependency khóa. Chi tiết nguồn giả, kịch bản nhãn và giới hạn ở `eval/README.md`. Đây là contract fixture, không thay schema parse production hoặc quy tắc chấm điểm ở bước 9.
- `eval/run_parse_eval.py`: độ chính xác theo trường (exact match cho email/phone/tên; F1 cho kỹ năng).
- `eval/run_score_eval.py`: so `ai_level` với nhãn; precision@10, mức đồng thuận (Cohen's kappa); chạy được trên bộ công khai (xem `docs/research/datasets.md`) và trên bộ CV nội bộ đã ẩn danh đặt ngoài repo (`EVAL_DATA_DIR`).
- `eval/run_bias_check.py`: cùng một CV, thay tên nam/nữ và các tên vùng miền khác nhau → mức chênh `ai_score`; báo cáo nếu chênh > 5 điểm.
- Kết quả ghi `eval/reports/<ngày>-<model>-<prompt_version>.md`. Đổi model hoặc prompt phải chạy lại.
