# T15 · Hồ sơ ứng viên và phản hồi AI
Mốc: M1 · Phụ thuộc: T14 · Spec: `03` (`GET /applications/{id}`, `/ai-feedback`, `/notes`, `PATCH /candidates/{id}`), `05` (màn 6)

## Việc cần làm
- API chi tiết application (kèm ứng viên, file CV, kết quả AI, activities); phản hồi AI (upsert theo user), ghi activity `ai_feedback`; ghi chú; sửa thông tin ứng viên.
- UI drawer: xem CV gốc (PDF viewer qua endpoint download; DOCX hiển thị `extracted_text`), mục Thông tin sửa được, mục **Đánh giá của AI** (nhãn mức, lý do, bảng tiêu chí ✓/~/✗/? kèm trích dẫn, cờ cảnh báo dịch sang tiếng Việt), nút Đồng ý / Không đồng ý (khi không đồng ý: chọn mức đúng + ghi chú), lịch sử hoạt động, ô thêm ghi chú.
- Khi `ai_level = insufficient`: hiện câu "CV thiếu thông tin để đánh giá — hãy xem trực tiếp".

## Tiêu chí nghiệm thu
- Test API: phản hồi lần 2 của cùng user ghi đè lần 1; recruiter không có quyền Job → 403; mở chi tiết ghi audit `candidate.view`.
- Không chỗ nào trên UI hiện chữ "LLM", "embedding", "prompt", "JSON".
