# T17 · Xuất Excel và audit log
Mốc: M1 · Phụ thuộc: T14 · Spec: `03` (`/jobs/{id}/export.xlsx`), `07` (audit)

## Việc cần làm
- Migration mới thêm cột `audit_log.details` (jsonb, mặc định `{}`) theo `02-data-model.md`; ghi `record_count` cho `candidate.export`. Thay đổi schema này đã được duyệt, không cần dừng chờ.
- `app/services/audit.py` dùng chung (nếu chưa có), áp dụng cho xem/tải CV, export.
- Export bảng xếp hạng Job ra `.xlsx` (openpyxl): họ tên, email, SĐT, mức AI (tiếng Việt), điểm, lý do (gộp), kỹ năng, năm KN, stage, ngày nhận; định dạng tiêu đề đậm, cố định hàng đầu, độ rộng cột hợp lý, tên file `ung-vien-<slug-job>-<ngày>.xlsx`.
- Nút "Xuất Excel" ở tab Ứng viên; xác nhận "File chứa dữ liệu cá nhân, chỉ chia sẻ nội bộ".

## Tiêu chí nghiệm thu
- Test: file mở được bằng openpyxl, số dòng đúng, tiếng Việt hiển thị đúng; audit có `candidate.export` với số bản ghi.
