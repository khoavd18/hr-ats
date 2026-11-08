# T29 · Đồng ý, thời hạn lưu, yêu cầu xoá
Mốc: M5 · Phụ thuộc: T18 · Spec: `07` (Dữ liệu cá nhân), `03` (Quản trị dữ liệu, consent)

## Việc cần làm
- API ghi nhận đồng ý; nhắc trên drawer khi `consent_at` trống.
- Job `enforce_retention` hằng ngày: đánh dấu hết hạn, sau 30 ngày xoá vĩnh viễn file (Storage), `extracted_text`, `anonymized_text`, `parsed_json`, embedding, thông tin liên hệ; giữ application/stage_events ẩn danh cho thống kê.
- `data_requests` + thực thi xoá ngay (admin), ghi audit `candidate.purge`.
- UI Cài đặt > Lưu trữ dữ liệu: danh sách sắp hết hạn (gia hạn 1 năm nếu có đồng ý mới), yêu cầu xoá, nhật ký audit (lọc theo người/hành động).

## Tiêu chí nghiệm thu
- Test: sau purge, file không còn trong Storage và mọi trường cá nhân là null; báo cáo KPI vẫn tính đúng số lượng cũ.

## Ghi chú từ review T05
- `audit_log.actor_id` đang `NOT NULL`, trong khi job tự động `enforce_retention` không có người thực hiện. Cho phép `actor_id` null (hệ thống) bằng migration mới, hoặc ghi rõ actor hệ thống, trước khi ghi audit `candidate.purge` từ job nền.
