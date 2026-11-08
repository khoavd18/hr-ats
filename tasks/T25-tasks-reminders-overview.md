# T25 · Task, nhắc việc, trang Tổng quan
Mốc: M4 · Phụ thuộc: T21 · Spec: `02` (tasks), `03` (Task & hoạt động), `06` (Task và nhắc việc), `05` (màn 2, 8)

## Việc cần làm
- Model + migration + API `tasks`; activity `task_done` khi hoàn thành.
- Job Beat: tự tạo task theo 2 quy tắc trong `06` (không tạo trùng nếu task mở cùng loại đã tồn tại); `remind_due_tasks` 8:00 gửi email tổng hợp.
- UI "Việc của tôi" (nhóm Quá hạn / Hôm nay / Sắp tới, tick hoàn thành, tạo việc gắn Job/ứng viên) và nút "Tạo việc cần làm" trong drawer.
- Trang Tổng quan theo `05` màn 2.

## Tiêu chí nghiệm thu
- Test quy tắc tự tạo task (có và không tạo trùng), email nhắc việc chỉ gửi cho người có task đến hạn.
