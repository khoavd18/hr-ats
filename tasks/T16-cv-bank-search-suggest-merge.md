# T16 · Kho CV: tìm kiếm, gợi ý, gộp trùng
Mốc: M1 · Phụ thuộc: T15 · Spec: `03` (CV & ứng viên, `/jobs/{id}/suggestions`), `04` (Tìm kiếm, bước 4), `05` (màn 7, tab Ứng viên nút "Thêm từ kho CV")

## Việc cần làm
- API tìm kiếm full-text có lọc; tìm theo nghĩa; gợi ý ứng viên cho Job; gộp trùng (chuyển cv_files, applications sang ứng viên đích, đánh dấu `merged_into_id`, soft delete bản nguồn, ghi activity).
- UI `/candidates`: ô tìm kiếm, công tắc "Tìm theo ý nghĩa", bộ lọc, danh sách thẻ ứng viên (tên, chức danh, năm KN, kỹ năng chính, nguồn, ngày nhận), nhãn "Có thể trùng" + hộp gộp (so sánh hai bên), nút "Thêm vào việc tuyển dụng…".
- Trong Job: hộp "Thêm từ kho CV" hiện gợi ý, chọn nhiều → tạo application và chấm.

## Tiêu chí nghiệm thu
- Test: tìm "ke toan" ra CV có "Kế toán"; gợi ý không trả ứng viên đã có trong Job; gộp xong không còn application trùng cho cùng Job.
