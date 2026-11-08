# T18 · Seed dev và E2E lát cắt đầu tiên
Mốc: M1 · Phụ thuộc: T16, T17 · Spec: `02` (Seed dev), `08`

## Việc cần làm
- `app/scripts/seed.py` theo `02` (dùng CV trong `data/sample_cvs/`, chạy pipeline thật với FakeLLM), idempotent, in ra tài khoản dev.
- Playwright: test `m1-smoke.spec.ts`: đăng nhập recruiter → tạo Job từ `jobs.json` → kéo thả 5 CV mẫu → chờ xử lý xong → bảng có 5 dòng, dòng đầu là mức cao nhất theo nhãn → mở drawer → bấm "Không đồng ý", chọn mức khác → thấy ghi nhận → tìm trong Kho CV theo kỹ năng → thấy ứng viên.
- README: mục "Demo nhanh" (các lệnh từ khởi động hạ tầng đến mở trình duyệt).

## Tiêu chí nghiệm thu
- Từ repo sạch, làm theo README "Demo nhanh" chạy được và E2E pass.
- Đánh dấu mốc **M1 hoàn thành** trong `tasks/PROGRESS.md`.
