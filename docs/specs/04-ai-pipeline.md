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

T24: sau commit `process_cv_file` done, file source=email được đưa qua
`queue_receipt` để gửi riêng mẫu cv_received theo spec 06. Lỗi email không
rollback parse/embedding/score. File failed hoặc nguồn upload không tự gửi.
Ứng viên mới dùng source từ file; dedupe giữ nguồn của ứng viên đã có.
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

T10: `parse_cv(text, client=None, version=1)` trả `ParseResult(parsed: ParsedCV,
model, prompt_version)`. `ParsedCV` gộp ba schema T09, không có email/phone;
`ParseResult` không hiện dữ liệu parse trong repr. Ba prompt riêng T09 dùng cùng
version, render trước rồi gọi qua `ThreadPoolExecutor(max_workers=3)`, không truyền
session DB vào thread. Retry/validate do adapter T09 đảm nhiệm, không nhân thêm
retry ở tầng parse; một phần lỗi thì không trả kết quả thiếu phần.

## 4. Chống trùng (`services/dedupe.py`)
- Khớp tuyệt đối: cùng email hoặc cùng phone chuẩn hoá → gắn file vào ứng viên cũ, cập nhật thông tin mới nhất.
- Không có email/phone: cosine embedding > 0.95 **và** tên chuẩn hoá (bỏ dấu, chữ thường) trùng → đánh dấu "có thể trùng" để người dùng gộp, không tự gộp.
- Cùng `sha256` file → không xử lý lại, trả về bản ghi cũ.

### Contract triển khai T10

- SHA-256 vẫn xử lý tại upload T07, kiểm quyền trước khi trả record cũ, không gọi
  lại parse. Worker khoá hàng `cv_files` đến cuối transaction; `done`/`failed` là
  trạng thái kết thúc, delivery lặp không ghi lại. `pending`/`running` được xử lý.
  ASSUMED (#43): `running` chỉ flush trong transaction nên bên đọc có thể vẫn thấy
  `pending` đến khi commit. Crash rollback về trạng thái trước; delivery lại có
  thể xử lý tiếp. Một savepoint bao toàn pipeline; lỗi rollback mọi thay đổi file/
  Candidate dở dang rồi lưu riêng `failed` và lỗi tiếng Việt cố định của bước.
  Không lưu/log exception gốc; lỗi OCR local giữ thông báo an toàn T08. DB mất
  kết nối hoàn toàn vẫn cần phục hồi DB trước khi ghi được trạng thái.
- File thành công lưu text gốc trích cục bộ, method/page_count, parsed_json không
  liên hệ, parse_model và parse_prompt_version. Chỉ text đã che email/SĐT được
  đưa vào cả ba prompt. Email lowercase, phone canonical từ bước 2 được ghi thẳng
  Candidate; không lấy liên hệ do LLM sinh.
- `match_candidate` xét mọi liên hệ trích được, bỏ Candidate đã xoá/đã gộp.
  Một advisory transaction lock chung trong namespace riêng nối khâu tìm và ghi
  Candidate để hai file khác hash đến đồng thời không tạo hai người cùng liên hệ.
  Đây là mặc định đơn giản cho M1, chưa benchmark tải production. ASSUMED (#41):
  khớp nhiều Candidate khác nhau → file failed để HR kiểm tra, không tự chọn/gộp.
  Liên hệ đầu tiên là liên hệ chính khi cập nhật; trường null/mảng rỗng nghĩa là
  chưa biết, giữ thông tin cũ; giá trị mới có dữ liệu thay thông tin cũ.
- ASSUMED (#42): ngày nhận tính theo `TZ`; `retention_until` bằng ngày đó cộng
  `DATA_RETENTION_MONTHS` tháng lịch (số dương, mặc định 24), cuối tháng giới hạn
  về ngày cuối tháng đích. CV mới cùng người cập nhật lại thời hạn; không tự tạo
  bằng chứng đồng ý, giữ consent đã có. Khi không trích được tên, parsed_json vẫn
  null, Candidate dùng nhãn "Chưa xác định" vì cột full_name bắt buộc.
- `anonymize_and_embed(session, candidate, text)` và
  `create_and_score_application(session, candidate, cv_file)` là hook cho
  T11/T12 tại T10; T11 đã nối hook đầu, T12 đã nối hook application/chấm điểm.
  Không đổi stage/gửi email.
  ASSUMED (#44): chỉ tìm nghi trùng khi CV không có liên hệ và sau hook có vector
  khác zero. Tên bỏ dấu/đ/hoa thường và gộp khoảng trắng; cosine > 0.95, chọn
  gần nhất, hoà thì theo ID. Chỉ ghi UUID `possible_duplicate_of` vào parsed_json
  của file mới, không gộp Candidate. Thiếu embedding thì chưa có kết luận nghi
  trùng; T11 đã nối hook và bật bước này.

## 5. Ẩn danh (`ai/anonymize.py`)
Tạo `anonymized_text` từ text đã che: thay họ tên (cả dạng có dấu, không dấu, viết hoa) bằng `[TÊN]`; xoá dòng ngày sinh/tuổi, giới tính ("Nam", "Nữ", "Giới tính"), tình trạng hôn nhân, địa chỉ nhà, link mạng xã hội cá nhân. Có test với ít nhất 15 mẫu CV giả.
**Chỉ `anonymized_text` được dùng cho embedding và chấm điểm.**

T11: `anonymize(text, full_name) -> str` chạy cục bộ, NFC, gọi lại redaction liên
hệ để bảo vệ cả caller ngoài pipeline. Thay tên theo ranh giới từ, bỏ dấu/đ/hoa
thường khi so khớp nhưng giữ nguyên dấu trong nội dung nghề nghiệp. Thu thập thêm
tên từ dòng có nhãn; nếu không che được tên thì che dòng đầu chỉ gồm 2–6 từ chữ
cái như một header có thể chứa tên, không lưu tên suy đoán. Xoá cả dòng metadata
VI/EN về ngày/năm sinh, tuổi, giới tính, hôn nhân, địa chỉ; nhãn riêng một dòng
thì bỏ thêm dòng giá trị kế tiếp. Bỏ link mạng xã hội/profile cá nhân phổ biến
(gồm GitHub/GitLab); giữ link tài liệu kỹ thuật. Ảnh không vào text từ extraction;
bỏ thêm markup ảnh Markdown/HTML nếu có trong text. ASSUMED (#46): heuristic này
không phải NER đầy đủ, có thể bỏ header nghề nghiệp khi parse không nhận ra tên;
không bảo đảm phát hiện PII bị OCR sai hoặc không có nhãn trong mọi CV thực tế.
Test dùng 50 CV kỹ thuật số giả, không phải đánh giá chất lượng trên CV thật.

## 6. Embedding (`ai/embed.py`)
Interface `Embedder.embed(texts) -> list[list[float]]`; bản `LocalEmbedder` (sentence-transformers, chuẩn hoá L2) và `FakeEmbedder` (hash tất định, cho test). Embedding cho Job lấy từ `title + description + must_have + nice_to_have`.

T11: `get_embedder(settings=None)` chọn đúng provider, không tự fallback. Fake
dùng SHA-256 từng từ Unicode NFC/casefold, cộng vào chiều và dấu tất định rồi L2;
text rỗng dùng vector đơn vị, batch rỗng trả []. Fake chỉ phục vụ kiểm thử chức
năng, không thể chứng minh chất lượng tìm kiếm ngữ nghĩa. Local lazy-load và
cache một model trong process, cache trọng số tại `var/models`,
`trust_remote_code=False`, chỉ safetensors, tắt progress bar. APP_ENV=test chỉ
đọc model local; unit test thay boundary thư viện, không tải trọng số/mạng ngoài.
Mọi kết quả phải đủ batch, đúng EMBEDDING_DIM, hữu hạn, khác zero và L2 chuẩn hoá;
sai trả `EmbeddingError` cố định, không log/lưu text hay exception gốc.

`services/embeddings.embed_candidate` chỉ truyền kết quả `anonymize` cho adapter;
ghi `anonymized_text` và vector sau khi thành công, cùng savepoint pipeline T10.
`embed_job(job, ...)` lấy bốn trường trên theo thứ tự, phân cách xuống dòng;
T13 gọi sau khi gán trường lúc tạo/sửa và trước commit, không dùng ORM event hay
tự commit. API tìm kiếm/quyền/filter top-50 vẫn thuộc T16, T11 chỉ kiểm truy vấn
cosine PostgreSQL qua test. Không đổi schema/dimension vector.

ASSUMED (#47): dependency local nặng nằm trong extra `local-embedding`,
`uv sync` mặc định vẫn đủ chạy fake/CI. Với local dùng
`uv sync --extra local-embedding` và cùng extra cho các lệnh uv run. Lần dùng local đầu tiên tải
model cấu hình; không tải model trong test. Tham khảo tham số chính thức:
[SentenceTransformer](https://sbert.net/docs/package_reference/sentence_transformer/model.html).

ASSUMED (#48): `uv run python -m app.scripts.reembed --all` tính lại toàn bộ
ứng viên chưa xoá/chưa gộp/còn hạn lưu từ `anonymized_text` đã lưu (che lại cục
bộ), cùng tất cả Job. Xoá vector cũ của ứng viên không còn hợp lệ, không đọc CV
gốc/không gọi parse. Thiếu text đã ẩn danh, sai chiều hoặc lỗi bất kỳ → rollback
toàn lượt; không bỏ qua rồi trộn hai không gian vector. CLI chỉ in số lượng và
mã lỗi. Dừng mọi writer và chức năng tìm kiếm trước khi đổi model/provider và
chạy lại; chỉ bật lại sau khi command commit thành công. Metadata model theo
cấu hình triển khai, không thêm cột ngoài schema spec. Đổi dimension vẫn cần
migration riêng theo spec 01/README, CLI không tự thay schema. Chưa benchmark
transaction toàn bộ kho ở quy mô production.

## 8. Chấm theo tiêu chí (`ai/score.py`, prompt `prompts/score_cv/v1.md`)
Đầu vào: `anonymized_text`, danh sách `must_have`, `nice_to_have`, tiêu đề và mô tả Job.
LLM trả cho **từng tiêu chí**:
```json
{"criterion": "3 năm kinh nghiệm Java", "kind": "must", "result": "met|partial|not_met|unknown",
 "evidence": "trích ngắn ≤ 20 từ từ CV hoặc null"}
```
cùng `reasons` (2–3 câu tiếng Việt, ngắn, không nhắc tên/giới tính/tuổi) và `flags` (mảng mã: `job_hopping`, `employment_gap`, `missing_must_have`, `overqualified`, `unclear_cv`).
`evidence` phải là chuỗi có thật trong `anonymized_text` (code kiểm tra; nếu không khớp thì đặt `result = unknown`).

T12: `score_cv(anonymized_text, *, job_title, job_description, must_have,
nice_to_have, client=None, version=1)` trả `ScoreResult(judged: ScoreOutput,
model, prompt_version)`; nội dung không xuất trong repr. Chỉ truyền text đã ẩn
danh, không đọc CV gốc/identity. Output phải giữ đúng số lượng/thứ tự/nguyên văn
tiêu chí và kind của Job (kể cả tiêu chí lặp); thiếu/thêm/đổi → lỗi output, không
tự sửa trọng số hoặc chấm thiếu tiêu chí. Retry schema/transport do adapter T09
đảm nhiệm. So bằng chứng sau NFC và gộp mọi khoảng trắng, phân biệt hoa/thường
và dấu; bằng chứng null/rỗng/không khớp → `unknown`, xoá evidence sai. Đây chỉ là
kiểm trích dẫn tồn tại, chưa chứng minh trích dẫn có hàm ý đúng với tiêu chí.

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

T12: cấu hình môi trường `SCORE_MUST_WEIGHT=0.75` (nice = 1 − must),
`SCORE_PARTIAL_VALUE=0.5`, `SCORE_HIGH_THRESHOLD=75`,
`SCORE_UNKNOWN_THRESHOLD=0.5`, `SCORE_MIN_TEXT_LENGTH=300`; validate miền giá trị,
không nhận NaN/Infinity. `round` theo Python (tie to even). Không có must →
must_score=0; không có tiêu chí → score=0, level=insufficient. Độ dài tính theo
text đã ẩn danh. Không đổi stage, owner, rejected_reason hoặc gửi email.

### Application và worker T12

- Upload có Job: cùng transaction T10 tạo Application stage=new, owner=owner Job;
  unique partial index hiện có chống trùng candidate/job. CV revision cùng người
  và Job dùng Application chưa xoá, xoá kết quả cũ/đặt pending, giữ stage/owner.
  File đã done/sha256 trùng vẫn không chạy lại. Hook trả ID; chỉ publish
  `score_application` queue ai sau commit file/Candidate/Application.
- Worker khoá hàng Application, chỉ xử lý pending/running; done/failed hoặc đã
  xoá thì bỏ qua delivery lặp. Không chấm Candidate đã xoá/gộp/hết hạn. Thiếu
  anonymized_text → failed, không fallback sang extracted_text/parsed_json.
  Savepoint bao score + activity `ai_scored` (actor null, payload chỉ level/score).
  Thành công lưu toàn bộ ai_* cùng model/v1/thời điểm UTC; lỗi rollback rồi xoá
  kết quả dở, chỉ đặt ai_status=failed, không log/lưu exception provider/CV.
  Crash rollback về pending và delivery lại xử lý được. running chỉ flush như T10.
- Chấm lại một Application: kiểm quyền, khoá/reset pending và commit trước publish.
  `rescore_job` duyệt Application chưa xoá, bỏ Candidate không hợp lệ; reset/
  commit/publish từng hồ sơ riêng, một lỗi chấm hoặc publish không chặn hồ sơ sau.
  Mỗi yêu cầu chấm lại thành công ghi activity mới; worker score delivery lặp
  không ghi trùng. Bulk task delivery lặp có thể tạo một lượt chấm lại mới.
- Lỗi publish score đặt pending → failed; không đổi CV done hoặc ghi đè score đã
  done nếu dispatch timeout sau thành công. HR dùng endpoint rescore để thử lại.
  ASSUMED (#51): chưa thêm outbox/schema ngoài spec; crash giữa commit và publish
  có thể để pending, cần chấm lại khi worker/broker đã phục hồi.
- FakeLLM vẫn offline, không đọc jobs.json/nhãn: so từ khoá có ranh giới từ,
  đọc mục kỹ năng dạng nhãn hoặc heading riêng dòng; dùng trích dẫn danh sách
  kỹ năng cho từ khoá không có. Kinh nghiệm dùng số năm ghi rõ VI/EN: đủ → met,
  có nhưng thiếu → partial, zero → not_met, thiếu thông tin → unknown.
  Đây là heuristic fixture để kiểm pipeline, không phải quy tắc đánh giá CV thật.

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

T16 nối ba truy vấn qua API có quyền, DTO tóm tắt và filter tại spec 03/T16.
Semantic dùng adapter T11 cho câu kỹ năng/chức danh, che liên hệ/metadata có nhãn
cục bộ trước khi gọi; không đưa raw CV vào tìm kiếm. Fake không đánh giá được
chất lượng ngữ nghĩa. Tên ứng viên cụ thể tìm bằng full-text. Gợi ý dùng vector
Job đã lưu, không gọi LLM, không tự tạo hồ sơ. HR chọn nhiều mới gọi T12 tạo và
chấm theo workflow hiện có.

Nghi trùng T10 chỉ là UUID gợi ý, đọc theo lô và bỏ bên đã hết hạn/xoá/gộp.
Gộp cần admin/lead xác nhận so sánh hai bên; giữ dữ liệu bản đích, chuyển file/
Application, soft delete nguồn và Application xung đột, activity metadata chung
transaction. Không tự chấm lại/đổi stage hoặc suy diễn đồng ý. Khoá Candidate ở
T12 chống request thêm hồ sơ bằng nguồn vừa bị gộp. Chi tiết xung đột/lịch sử và
quyền ở contract T16 spec 03; không thêm bước AI hoặc schema.

## Đánh giá (`eval/`)
- `eval/generate_synthetic_cvs.py`: sinh CV giả tiếng Việt (DOCX + PDF, 1 cột, 2 cột, có bảng, bản ảnh scan có nhiễu) cùng file nhãn JSON (thông tin đúng + mức phù hợp với vài Job mẫu).
- T06: chạy tại `backend/` bằng `uv run python ../eval/generate_synthetic_cvs.py --count 60 --seed 20261108 --out ../data/sample_cvs`; mặc định đầu ra là `data/sample_cvs/` ở gốc repo. Schema nhãn version 1 dùng `CVLabel`/`JobDataset` trong `eval/schemas.py`: mỗi CV có `<id>.json`, `synthetic=true`, trường parse đúng và `expected_level[job_id]`; `jobs.json` có năm Job cùng ma trận `expected_level[cv_id][job_id]`. Nhãn `high|medium|low|insufficient`; metadata/ZIP/font/random cố định để sinh lại cùng byte với dependency khóa. Chi tiết nguồn giả, kịch bản nhãn và giới hạn ở `eval/README.md`. Đây là contract fixture, không thay schema parse production hoặc quy tắc chấm điểm ở bước 9.
- `eval/run_parse_eval.py`: độ chính xác theo trường (exact match cho email/phone/tên; F1 cho kỹ năng).
- `eval/run_score_eval.py`: so `ai_level` với nhãn; precision@10, mức đồng thuận (Cohen's kappa); chạy được trên bộ công khai (xem `docs/research/datasets.md`) và trên bộ CV nội bộ đã ẩn danh đặt ngoài repo (`EVAL_DATA_DIR`).
- `eval/run_bias_check.py`: cùng một CV, thay tên nam/nữ và các tên vùng miền khác nhau → mức chênh `ai_score`; báo cáo nếu chênh > 5 điểm.
- Kết quả ghi `eval/reports/<ngày>-<model>-<prompt_version>.md`. Đổi model hoặc prompt phải chạy lại.
