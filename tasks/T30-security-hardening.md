# T30 · Gia cố bảo mật
Mốc: M5 · Phụ thuộc: T29 · Spec: `07`

## Việc cần làm
- Test tham số hoá cho **toàn bộ** bảng quyền `07` × endpoint liên quan.
- Rà soát log: test chạy pipeline đầy đủ và kiểm tra log không chứa email/SĐT/họ tên mẫu.
- Header bảo mật (CSP cơ bản, X-Content-Type-Options, Referrer-Policy) cho API và web; giới hạn tốc độ đăng nhập và upload.
- Chạy skill `secure-code-review` trên backend và ghi kết quả vào `docs/security/review-<ngày>.md`, sửa mục mức cao.

## Tiêu chí nghiệm thu
- Bộ test quyền pass; không còn phát hiện mức cao chưa xử lý trong báo cáo review.

## Ghi chú từ review T24
- F2: `recover_intake` (`backend/app/email/inbound.py`) chọn lại mỗi lần poll các CV nguồn email đã xử lý nhưng không có email ứng viên, với `limit(100)`. Khi có trên 100 CV như vậy, các CV khác không bao giờ được gửi `cv_received`. Đánh dấu đã xử lý (hoặc loại khỏi truy vấn) các CV không có email; thêm test với hơn 100 bản ghi.
- F1: lỗi đọc kích thước thư IMAP đang báo chung mã `IMAP_MESSAGE_TOO_LARGE`; tách mã lỗi riêng.
