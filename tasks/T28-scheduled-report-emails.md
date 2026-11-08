# T28 · Email báo cáo định kỳ
Mốc: M4 · Phụ thuộc: T23, T26 · Spec: `06` (Báo cáo định kỳ)

## Việc cần làm
- Job `generate_daily_report` (18:00) và `generate_weekly_report` (8:30 thứ Hai), giờ Việt Nam; email HTML bảng KPI cho lead/admin, link về trang Báo cáo.
- Lệnh chạy tay: `uv run python -m app.scripts.send_report --daily|--weekly --dry-run` (in HTML ra file để xem trước).

## Tiêu chí nghiệm thu
- Test: lịch Beat đúng giờ theo múi giờ; nội dung email khớp số từ `queries.py`; không gửi cho recruiter.
