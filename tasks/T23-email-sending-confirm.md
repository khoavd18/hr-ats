# T23 · Gửi email có xác nhận
Mốc: M3 · Phụ thuộc: T20, T21, T22 · Spec: `06` (Luồng gửi), `03` (`/move`, Email)

## Việc cần làm
- `move` trả `suggested_email` khi stage đích có mẫu đang bật (render sẵn subject/body, `to_email` = email ứng viên; với `submitted` = email liên hệ của đơn vị tuyển). Interview invite đính kèm .ics.
- API tạo nháp, gửi (`queued`), huỷ; worker `send_email_message` qua SMTP với retry 1/5/15 phút, giới hạn tốc độ, lưu `message_id`, activity `email_sent`.
- UI: dialog xem trước sau khi kéo thả (sửa được, nút "Gửi" / "Không gửi"), mục Email trong drawer (danh sách đã gửi/lỗi, nút gửi lại khi lỗi, soạn email tự do từ mẫu).

## Tiêu chí nghiệm thu
- Test với Mailpit (hoặc SMTP giả trong bộ nhớ khi test): kéo sang Phỏng vấn → có nháp, chưa gửi; bấm Gửi → mail đến Mailpit có .ics; ứng viên không có email → không gợi ý gửi và UI báo rõ.
- Không có đường nào gửi email `interview_invite`, `rejection`, `offer`, `submitted_to_unit` mà không qua bước bấm Gửi.
