# T21 · Phỏng vấn, offer, placement
Mốc: M2 · Phụ thuộc: T19 · Spec: `02` (interviews, offers, placements), `03` (mục tương ứng), `05` (màn 6)

## Việc cần làm
- Model + migration + API cho `interviews`, `offers`, `placements`; tạo interview đầu tiên tự chuyển application sang `interview` (qua `pipeline.move`); tạo offer `sent` → stage `offer`; tạo placement → stage `hired`.
- `GET /interviews/{id}/ics` sinh file iCalendar (múi giờ Asia/Ho_Chi_Minh).
- `GET /interviews?from=&to=&mine=true` cho trang Tổng quan.
- UI trong drawer: Đặt lịch phỏng vấn (ngày giờ, thời lượng, địa điểm/link, người phỏng vấn), cập nhật kết quả + feedback; tạo offer; ghi nhận nhận việc (ngày bắt đầu, phí nếu có, hạn bảo hành).

## Tiêu chí nghiệm thu
- Test: tạo interview chuyển stage đúng và ghi `stage_events`; file .ics hợp lệ (parse lại được); placement duy nhất cho mỗi application.
