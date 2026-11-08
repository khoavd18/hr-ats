# T13 · Đơn vị tuyển và Job
Mốc: M1 · Phụ thuộc: T05 · Spec: `03` (Đơn vị tuyển, Job), `05` (màn 3, 4, Cài đặt > Đơn vị tuyển)

## Việc cần làm
- API CRUD đơn vị tuyển và Job, members, lọc/tìm Job; `opened_at` khi chuyển `open`, `closed_at` khi `closed`; tính embedding Job (hook T11, dùng FakeEmbedder nếu T11 chưa xong).
- Khi sửa `must_have`/`nice_to_have` của Job đã có application → response có `needs_rescore: true`.
- UI: danh sách Job (cột theo `05`; tạm ẩn cột số ứng viên theo mức AI nếu API chưa có), form tạo/sửa với hai ô danh sách yêu cầu, chọn đơn vị tuyển, người phụ trách, thành viên; hộp hỏi "Chấm lại tất cả ứng viên?" khi `needs_rescore`.
- Cài đặt > Đơn vị tuyển (admin/lead).

## Tiêu chí nghiệm thu
- Test API: recruiter chỉ thấy Job của mình; validate (tiêu đề bắt buộc, `salary_min ≤ salary_max`, ít nhất 1 yêu cầu bắt buộc khi chuyển `open`).
- Test UI (Vitest): form báo lỗi tiếng Việt khi thiếu tiêu đề.
