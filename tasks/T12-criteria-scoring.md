# T12 · Chấm điểm theo tiêu chí
Mốc: M1 · Phụ thuộc: T11 · Spec: `04` bước 8–9

## Việc cần làm
- `app/ai/score.py`: gọi LLM với `anonymized_text` + yêu cầu Job; kiểm `evidence` có thật trong text (so khớp sau chuẩn hoá khoảng trắng/NFC), sai thì `unknown`.
- `app/ai/scoring_rules.py`: công thức và ngưỡng theo spec, hằng số cấu hình được.
- Worker `score_application(application_id)` (cập nhật `ai_*`, activity `ai_scored`), `rescore_job(job_id)`.
- Pipeline T10: nếu `cv_files.job_id` có giá trị → tạo application (stage `new`, owner = owner Job) và xếp hàng chấm.
- Endpoint `POST /applications` (thêm từ kho), `POST /applications/{id}/rescore`, `POST /jobs/{id}/rescore`.

## Tiêu chí nghiệm thu
- Unit test bao phủ mọi nhánh của `ai_level` (high, medium, low, insufficient) và công thức điểm.
- Test evidence bịa → `unknown`.
- Test end-to-end với FakeLLM trên `data/sample_cvs/jobs.json`: ít nhất 70% CV có `ai_level` khớp `expected_level` (FakeLLM dựa từ khoá; nếu thấp hơn, chỉnh dữ liệu giả cho rõ ràng hơn chứ không chỉnh công thức).
