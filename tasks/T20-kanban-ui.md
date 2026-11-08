# T20 · Kanban
Mốc: M2 · Phụ thuộc: T19 · Spec: `05` (màn 5 tab Quy trình, Quy tắc chung)

## Việc cần làm
- Tab Quy trình: cột theo stage (ẩn `withdrawn` vào menu "Xem thêm"), thẻ ứng viên (tên, mức AI, ngày ở stage hiện tại), kéo thả bằng dnd-kit, cập nhật lạc quan và quay lại nếu API lỗi.
- Kéo vào "Không phù hợp" → hộp chọn lý do bắt buộc.
- Toast "Đã chuyển … sang …" có nút **Hoàn tác** (gọi `/undo`).
- Chỗ gắn hộp xem trước email (để T23 dùng): khi API trả `suggested_email` khác null thì mở dialog.

## Tiêu chí nghiệm thu
- Test component: kéo thẻ gọi API đúng; lỗi API → thẻ quay về cột cũ + thông báo; hoàn tác hoạt động.
