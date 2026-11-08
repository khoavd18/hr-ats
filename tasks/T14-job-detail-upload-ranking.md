# T14 · Chi tiết Job: upload và bảng xếp hạng
Mốc: M1 · Phụ thuộc: T12, T13 · Spec: `03` (`GET /jobs/{id}/applications`), `05` (màn 5 tab Ứng viên, Quy tắc chung)

## Việc cần làm
- API danh sách application của Job: lọc `stage`, `ai_level`, `q`; sắp mặc định theo mức AI rồi `ai_score` giảm dần; trả thêm thống kê số lượng theo mức AI (dùng lại cho cột ở danh sách Job).
- UI trang `/jobs/[id]` với 3 tab (tab Quy trình và Thông tin là khung, hoàn thiện ở T20/T13).
- Tab Ứng viên: vùng kéo thả nhiều file (hiện tiến trình từng file: "Đang tải lên" → "Đang đọc CV…" → "AI đang đánh giá…" → xong/lỗi), polling 3 giây; bảng xếp hạng theo `05` với `AiLevelBadge`; lọc theo mức AI và stage; click dòng mở drawer (khung, hoàn thiện ở T15).

## Tiêu chí nghiệm thu
- Kéo 10 CV mẫu vào Job mẫu (FakeLLM) → sau khi xử lý, bảng hiện 10 dòng sắp đúng thứ tự mức AI.
- File lỗi hiện thông báo tiếng Việt trên đúng dòng của file đó; các file khác vẫn xử lý.

## Ghi chú từ review T02
- Polling 3 giây sẽ tạo rất nhiều dòng log HTTP: hạ mức log (DEBUG) hoặc bỏ qua log cho `/api/v1/health` và các endpoint polling trong `backend/app/core/middleware.py`.
