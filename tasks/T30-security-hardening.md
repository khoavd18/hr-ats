# T30 · Gia cố bảo mật
Mốc: M5 · Phụ thuộc: T29 · Spec: `07`

## Việc cần làm
- Test tham số hoá cho **toàn bộ** bảng quyền `07` × endpoint liên quan.
- Rà soát log: test chạy pipeline đầy đủ và kiểm tra log không chứa email/SĐT/họ tên mẫu.
- Header bảo mật (CSP cơ bản, X-Content-Type-Options, Referrer-Policy) cho API và web; giới hạn tốc độ đăng nhập và upload.
- Chạy skill `secure-code-review` trên backend và ghi kết quả vào `docs/security/review-<ngày>.md`, sửa mục mức cao.

## Tiêu chí nghiệm thu
- Bộ test quyền pass; không còn phát hiện mức cao chưa xử lý trong báo cáo review.
