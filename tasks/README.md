# Task cho agent triển khai hr-ats

Đọc file này trước mỗi task. Spec nằm ở `docs/specs/`; quy tắc chung ở `AGENTS.md`.

Lệnh tắt cho agent: `Implement Txx` (`tasks/_implement.md`), `Review Txx` (`tasks/_review.md`), `Fix Txx` (`tasks/_fix.md`). Báo cáo review lưu ở `tasks/reviews/`.
Chạy tự động nhiều task trên máy dev: `.\scripts\auto-task.ps1 -From T03 -To T18` (dừng ở task nhạy cảm T04, T05, T23, T24, T29 để người duyệt merge, và sau mỗi mốc T04, T18, T21, T24, T28).
Trạng thái task trong `PROGRESS.md`: `todo` → `review` (agent làm xong) → `done` (đã review và merge) hoặc `blocked`.

## Quy trình cho mỗi task
1. Làm **đúng một task** mỗi lần, theo thứ tự trong bảng; chỉ bắt đầu khi các task phụ thuộc đã có trạng thái `done` trong `tasks/PROGRESS.md`.
2. Làm trên nhánh git `task/Txx-ten-ngan` (nếu repo có git).
3. Đọc mục "Spec cần đọc" của task trước khi code.
4. Chỉ sửa file trong phạm vi task. Không refactor phần khác, không đổi stack, không thêm dịch vụ ngoài spec.
5. Spec thiếu hoặc mâu thuẫn: chọn phương án đơn giản nhất phù hợp spec, ghi vào `docs/specs/open-questions.md`, tiếp tục. Chỉ dừng nếu không thể làm tiếp mà không đoán thay đổi lớn.
6. Chạy test và lint theo `docs/specs/08-testing-quality.md`; đáp ứng Definition of Done.
7. Ghi kết quả vào `tasks/PROGRESS.md` (đổi trạng thái task thành `done` hoặc `blocked`, kèm ghi chú).
8. Kết thúc bằng tóm tắt: đã làm gì, file chính, lệnh đã chạy và kết quả, việc còn lại.

## Danh sách task
| ID | Tên | Phụ thuộc | Mốc |
|---|---|---|---|
| T01 | Khung repo và hạ tầng dev | — | M0 Nền tảng |
| T02 | Khung backend | T01 | M0 |
| T03 | Khung frontend | T01 | M0 |
| T04 | Đăng nhập, người dùng, phân quyền | T02, T03 | M0 |
| T05 | Mô hình dữ liệu lõi | T04 | M1 Lọc CV dùng được |
| T06 | Sinh CV giả tiếng Việt | T01 | M1 |
| T07 | Lưu file, upload CV, Celery | T05 | M1 |
| T08 | Trích text và che thông tin liên hệ | T02, T06 | M1 |
| T09 | LLM adapter và prompt | T02 | M1 |
| T10 | Parse CV, chống trùng, pipeline xử lý | T07, T08, T09 | M1 |
| T11 | Ẩn danh và embedding | T10 | M1 |
| T12 | Chấm điểm theo tiêu chí | T11 | M1 |
| T13 | Đơn vị tuyển và Job (API + UI) | T05 | M1 |
| T14 | Chi tiết Job: upload và bảng xếp hạng | T12, T13 | M1 |
| T15 | Hồ sơ ứng viên và phản hồi AI | T14 | M1 |
| T16 | Kho CV: tìm kiếm, gợi ý, gộp trùng | T15 | M1 |
| T17 | Xuất Excel và audit log | T14 | M1 |
| T18 | Seed dev và E2E lát cắt đầu tiên | T16, T17 | M1 |
| T19 | Service pipeline và API | T18 | M2 Pipeline |
| T20 | Kanban | T19 | M2 |
| T21 | Phỏng vấn, offer, placement | T19 | M2 |
| T22 | Mẫu email | T19 | M3 Email |
| T23 | Gửi email có xác nhận | T20, T21, T22 | M3 |
| T24 | Nhận CV từ hộp mail | T23 | M3 |
| T25 | Task, nhắc việc, trang Tổng quan | T21 | M4 Task & báo cáo |
| T26 | Truy vấn KPI và API báo cáo | T21 | M4 |
| T27 | Giao diện báo cáo | T26 | M4 |
| T28 | Email báo cáo định kỳ | T23, T26 | M4 |
| T29 | Đồng ý, thời hạn lưu, yêu cầu xoá | T18 | M5 Chất lượng |
| T30 | Gia cố bảo mật | T29 | M5 |
| T31 | Bộ đánh giá AI | T12 | M5 |
| T32 | Triển khai và hướng dẫn sử dụng | T28, T30 | M5 |
| T33 | Bộ E2E hồi quy | T32 | M5 |

**Mốc M1** là bản đầu tiên HR dùng được: tạo Job, kéo thả CV, xem xếp hạng có lý do, phản hồi AI, tìm trong kho CV, xuất Excel.

## Chạy song song
Các task không phụ thuộc nhau có thể giao cho agent khác nhau trên nhánh riêng, ví dụ: T02 ‖ T03 ‖ T06; T08 ‖ T09; T13 ‖ (T10 → T12); T20 ‖ T21 ‖ T22; T26 ‖ T25; T31 bất kỳ lúc nào sau T12. Không cho hai agent sửa cùng một migration cùng lúc: task có migration merge xong mới chạy task có migration tiếp theo.
