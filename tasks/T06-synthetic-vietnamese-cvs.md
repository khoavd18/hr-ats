# T06 · Sinh CV giả tiếng Việt
Mốc: M1 · Phụ thuộc: T01 · Spec: `04-ai-pipeline.md` (Đánh giá), `07` (Dữ liệu trong repo)

## Mục tiêu
Có bộ CV giả đa dạng, có nhãn, dùng cho test, seed và demo — không cần dữ liệu thật.

## Việc cần làm
- `eval/generate_synthetic_cvs.py` (chạy bằng `uv run` trong `backend`, dùng python-docx, reportlab hoặc PyMuPDF, Pillow): tham số `--count`, `--seed`, `--out data/sample_cvs`.
- Dữ liệu nguồn trong script: họ tên Việt (nam/nữ, ba miền), trường đại học, công ty giả, chức danh và kỹ năng cho ít nhất 6 nhóm nghề (IT backend, IT frontend, kế toán, kinh doanh, marketing, nhân sự), số điện thoại dạng hợp lệ nhưng giả (đầu số 09xx 000 xxx), email `@example.com`.
- Bố cục: 1 cột, 2 cột, dạng bảng, có ảnh đại diện giả (khối màu), bản tiếng Anh, bản ảnh scan (render PDF → ảnh, xoay nhẹ, nhiễu) — mỗi kiểu ít nhất 5 CV.
- Mỗi CV kèm `<id>.json`: thông tin đúng (họ tên, email, SĐT, năm KN, kỹ năng, kinh nghiệm) để đánh giá parse.
- `data/sample_cvs/jobs.json`: 5 Job mẫu (tiêu đề, mô tả, must_have, nice_to_have) và nhãn `expected_level` của từng CV với từng Job.
- Sinh sẵn 60 CV và commit (kích thước tổng < 30 MB).

## Tiêu chí nghiệm thu
- Chạy lại với cùng `--seed` cho kết quả giống hệt.
- Mọi email kết thúc bằng `@example.com`; không có tên công ty thật nổi tiếng.
- Có test kiểm tra mỗi file CV có file nhãn tương ứng và nhãn hợp lệ theo schema.
