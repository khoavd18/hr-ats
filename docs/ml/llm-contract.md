# LLM contract: hr-ats

Mọi giá trị UNKNOWN phải được người phụ trách chốt; không tự điền.

| Mục | Giá trị |
|---|---|
| Nhà cung cấp LLM được duyệt | UNKNOWN (ứng viên: Anthropic Claude, OpenAI) |
| Model id cố định | UNKNOWN |
| Dữ liệu được gửi cho LLM | Text CV đã che tên, ảnh, giới tính, tuổi, địa chỉ; JD của Job |
| Dữ liệu không được gửi | Ảnh chân dung, CCCD/hộ chiếu, số tài khoản, thông tin sức khoẻ |
| Model embedding | UNKNOWN (cần hỗ trợ tiếng Việt + tiếng Anh) |
| Phiên bản prompt | Lưu trong `prompts/`, mỗi lần đổi tăng version |

## Các tác vụ LLM
1. **Parse CV** → JSON theo schema cố định (thông tin liên hệ, học vấn, kinh nghiệm, kỹ năng, ngôn ngữ, số năm KN). Tách thành nhiều prompt nhỏ theo nhóm thông tin.
2. **Chấm điểm CV theo Job** → mức Cao / Trung bình / Thấp + điểm 0–100, đạt/không từng tiêu chí bắt buộc, 2–3 lý do, cờ cảnh báo.

## Bộ đánh giá
- 100–200 CV cũ đã ẩn danh, có kết quả tuyển dụng thật và đánh giá của recruiter.
- Chỉ số: độ chính xác trích xuất theo trường; tỉ lệ ứng viên tốt nằm trong top 10 (precision@10); mức đồng thuận AI–recruiter.
- Kiểm tra thiên lệch: chấm lại cùng CV khi đổi tên/giới tính; chạy lại mỗi khi đổi model hoặc prompt.

## Tiêu chí chấp nhận trước khi bật cho cả team
UNKNOWN: ngưỡng đồng thuận AI–recruiter do team chốt.
