# T26 · Truy vấn KPI và API báo cáo
Mốc: M4 · Phụ thuộc: T21 · Spec: `06` (KPI), `03` (Báo cáo), `docs/metrics/kpi-list.md`

## Việc cần làm
- `app/reports/queries.py`: mỗi KPI một hàm nhận `(from, to, filters)`; phạm vi dữ liệu theo quyền (recruiter chỉ của mình).
- API `summary`, `funnel`, `recruiters`, `ai-agreement`, `export.xlsx`.
- Cập nhật `docs/metrics/kpi-list.md`: thêm cột "Hàm trong code" và giữ `status: draft` (người dùng tự duyệt).

## Tiêu chí nghiệm thu
- Fixture dữ liệu dựng tay (vài Job, ứng viên, stage_events có thời điểm cụ thể) với kết quả kỳ vọng tính tay cho từng KPI; test so khớp chính xác, kể cả ranh giới ngày theo giờ Việt Nam.

## Ghi chú từ review T02
- Múi giờ app đang đọc từ biến hệ thống `TZ`, dễ bị máy chủ ghi đè và làm lệch ranh giới ngày của KPI. Cân nhắc biến riêng `APP_TIMEZONE` (cập nhật spec 01 và `.env.example`).
