# T19 · Service pipeline và API
Mốc: M2 · Phụ thuộc: T18 · Spec: `02` (Stage pipeline), `03` (`/applications/{id}/move`, `/undo`, `/jobs/{id}/pipeline`)

## Việc cần làm
- `app/services/pipeline.py`: `move(application, to_stage, actor, note, rejected_reason)` kiểm tra chuyển hợp lệ, cập nhật `stage`, `stage_entered_at`, ghi `stage_events` và activity `stage_changed`; `undo(application, actor)` hoàn tác lần đổi gần nhất trong 24 giờ (người đã đổi hoặc lead/admin), ghi một `stage_event` mới (không xoá cái cũ).
- `rejected` bắt buộc `rejected_reason` (danh sách lý do chuẩn: thiếu kỹ năng, thiếu kinh nghiệm, lương không phù hợp, ứng viên không phản hồi, đơn vị tuyển từ chối, khác).
- API `move` trả `suggested_email` = `null` ở task này (T23 bổ sung). API `pipeline` trả cột theo stage.
- Bổ sung nhãn stage vào `/config/public`.

## Tiêu chí nghiệm thu
- Test cho mọi cặp chuyển stage (hợp lệ/không hợp lệ), undo quá 24 giờ bị từ chối, undo bởi người khác (recruiter) bị từ chối.
