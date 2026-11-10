# Hướng dẫn sử dụng hệ thống tuyển dụng

> Dành cho cán bộ tuyển dụng (HR). Không cần kiến thức kỹ thuật.

---

## Mục lục

1. [Đăng nhập](#1-đăng-nhập)
2. [Tạo vị trí tuyển dụng (Job)](#2-tạo-vị-trí-tuyển-dụng-job)
3. [Tải CV lên hệ thống](#3-tải-cv-lên-hệ-thống)
4. [Đọc đánh giá AI](#4-đọc-đánh-giá-ai)
5. [Chuyển bước tuyển dụng (Kanban)](#5-chuyển-bước-tuyển-dụng-kanban)
6. [Gửi email cho ứng viên](#6-gửi-email-cho-ứng-viên)
7. [Xem báo cáo tuyển dụng](#7-xem-báo-cáo-tuyển-dụng)
8. [Tìm kiếm CV trong kho](#8-tìm-kiếm-cv-trong-kho)
9. [Xuất danh sách ứng viên ra Excel](#9-xuất-danh-sách-ứng-viên-ra-excel)
10. [Yêu cầu xoá dữ liệu ứng viên](#10-yêu-cầu-xoá-dữ-liệu-ứng-viên)
11. [Câu hỏi thường gặp](#11-câu-hỏi-thường-gặp)

---

## 1. Đăng nhập

1. Mở trình duyệt và truy cập địa chỉ hệ thống mà quản trị viên cung cấp.
2. Nhập **email** và **mật khẩu** của bạn.
3. Nhấn **Đăng nhập**.

> 💡 Nếu quên mật khẩu, liên hệ quản trị viên để được đặt lại.

<!-- [ẢNH CHỤP MÀN HÌNH: trang đăng nhập] -->

---

## 2. Tạo vị trí tuyển dụng (Job)

Trước khi nhận CV, bạn cần tạo **vị trí tuyển dụng** để AI biết cần tìm ứng viên như thế nào.

### Các bước:

1. Trên menu bên trái, chọn **Tuyển dụng** → **Vị trí tuyển dụng**.
2. Nhấn nút **+ Tạo vị trí mới** (góc phải trên).
3. Điền thông tin:
   - **Tên vị trí**: ví dụ "Kỹ sư phần mềm Backend"
   - **Mô tả công việc**: dán nội dung JD vào đây
   - **Yêu cầu bắt buộc**: liệt kê từng yêu cầu (AI sẽ ưu tiên kiểm tra những điều này)
   - **Yêu cầu thêm**: các kỹ năng là lợi thế nhưng không bắt buộc
4. Nhấn **Lưu**.

> 💡 Mô tả càng chi tiết, AI đánh giá càng chính xác. Nên liệt kê rõ từng yêu cầu thay vì viết thành đoạn văn dài.

<!-- [ẢNH CHỤP MÀN HÌNH: form tạo vị trí tuyển dụng] -->

---

## 3. Tải CV lên hệ thống

Hệ thống nhận CV dạng **PDF** hoặc **Word (.docx)**.

### Tải lên từ máy tính:

1. Mở vị trí tuyển dụng muốn nhận CV.
2. Nhấn tab **Ứng viên** → **Tải CV lên**.
3. Chọn file hoặc kéo thả nhiều file cùng lúc (tối đa 20 MB/file).
4. Nhấn **Tải lên**.

Hệ thống sẽ:
- Trích xuất nội dung CV
- Che thông tin nhận dạng cá nhân trước khi gửi cho AI
- Chấm điểm tự động (thường mất 1–3 phút mỗi CV)

> 💡 Bạn có thể tải lên nhiều CV cùng lúc. Hệ thống xử lý theo hàng đợi, không cần chờ từng file xong.

<!-- [ẢNH CHỤP MÀN HÌNH: giao diện tải CV] -->

---

## 4. Đọc đánh giá AI

Sau khi hệ thống xử lý xong, mỗi CV hiển thị:

### Mức đánh giá:
| Mức | Ý nghĩa |
|---|---|
| 🟢 **Cao** | Đáp ứng tốt các yêu cầu của vị trí |
| 🟡 **Trung bình** | Đáp ứng một phần, cần xem thêm |
| 🔴 **Thấp** | Chưa đáp ứng được yêu cầu chính |

### Cách xem chi tiết:

1. Nhấn vào tên ứng viên để mở hồ sơ.
2. Phần **Đánh giá AI** hiển thị:
   - Mức tổng thể và điểm số
   - 2–3 lý do ngắn gọn (tại sao được đánh giá như vậy)
   - Từng tiêu chí: ✅ Đạt / ❌ Không đạt / ❓ Không đủ thông tin

### Nếu bạn không đồng ý với AI:

Nhấn nút **Không đồng ý** → chọn lý do → nhấn **Xác nhận**. Phản hồi của bạn giúp cải thiện hệ thống.

> ⚠️ AI chỉ **gợi ý**, bạn là người quyết định cuối cùng. Không có CV nào bị loại tự động.

<!-- [ẢNH CHỤP MÀN HÌNH: hồ sơ ứng viên với đánh giá AI] -->

---

## 5. Chuyển bước tuyển dụng (Kanban)

Bảng Kanban giúp bạn theo dõi tiến trình của từng ứng viên.

### Các bước mặc định:
`Mới nhận` → `Xem xét` → `Phỏng vấn` → `Offer` → `Đã tuyển` / `Từ chối`

### Cách chuyển bước:

**Cách 1 – Kéo thả:** Kéo thẻ ứng viên từ cột này sang cột khác.

**Cách 2 – Từ hồ sơ:** Mở hồ sơ ứng viên → nhấn **Chuyển bước** → chọn bước mới.

### Hoàn tác nếu chuyển nhầm:

Sau khi chuyển bước, hiện thị thông báo **"Hoàn tác"** trong 10 giây. Nhấn vào đó để quay lại.

<!-- [ẢNH CHỤP MÀN HÌNH: bảng Kanban] -->

---

## 6. Gửi email cho ứng viên

Hệ thống hỗ trợ gửi email **mời phỏng vấn**, **thư từ chối**, và **offer**. Mọi email đều có bước xem trước và cần bạn xác nhận trước khi gửi.

### Gửi email mời phỏng vấn:

1. Mở hồ sơ ứng viên.
2. Nhấn **Gửi email** → chọn **Mời phỏng vấn**.
3. Chọn mẫu email (hệ thống tự điền tên ứng viên, tên vị trí...).
4. Chỉnh sửa nội dung nếu cần.
5. Xem trước email → nhấn **Gửi**.

### Gửi thư từ chối:

1. Mở hồ sơ ứng viên.
2. Nhấn **Gửi email** → chọn **Từ chối**.
3. Xem trước nội dung → nhấn **Xác nhận gửi**.

> 💡 Hệ thống **không tự động gửi** email từ chối hay offer. Bạn phải nhấn xác nhận.

<!-- [ẢNH CHỤP MÀN HÌNH: giao diện xem trước email] -->

---

## 7. Xem báo cáo tuyển dụng

### Báo cáo hằng ngày / hằng tuần:

1. Trên menu, chọn **Báo cáo**.
2. Chọn khoảng thời gian: Hôm nay / Tuần này / Tháng này / Tùy chỉnh.
3. Xem các chỉ số:
   - Số CV nhận được
   - Phân bổ theo mức đánh giá AI (Cao / Trung bình / Thấp)
   - Tiến trình theo vị trí tuyển dụng
   - Thống kê theo từng recruiter

> 💡 Hệ thống tự động gửi email báo cáo tóm tắt vào **8:00 SA hằng ngày** và **8:00 SA thứ Hai** hằng tuần đến địa chỉ email của bạn (nếu được bật).

<!-- [ẢNH CHỤP MÀN HÌNH: trang báo cáo] -->

---

## 8. Tìm kiếm CV trong kho

Kho CV lưu tất cả hồ sơ ứng viên đã từng nộp vào hệ thống.

### Tìm kiếm:

1. Chọn **Kho CV** trên menu.
2. Nhập từ khoá: tên, kỹ năng, trường học...
3. Lọc thêm theo: vị trí tuyển dụng, mức AI, trạng thái, thời gian.
4. Nhấn vào kết quả để xem hồ sơ đầy đủ.

### Gợi ý ứng viên:

Khi mở một vị trí tuyển dụng, nhấn **Gợi ý từ kho CV** để hệ thống tìm những ứng viên cũ phù hợp nhất.

<!-- [ẢNH CHỤP MÀN HÌNH: trang kho CV] -->

---

## 9. Xuất danh sách ứng viên ra Excel

1. Mở vị trí tuyển dụng.
2. Chọn tab **Ứng viên**.
3. Lọc nếu cần (theo bước, mức AI...).
4. Nhấn **Xuất Excel**.
5. File `.xlsx` sẽ được tải về máy tính của bạn.

File Excel bao gồm: tên ứng viên, vị trí ứng tuyển, mức AI, trạng thái, ngày nhận CV, và ghi chú.

<!-- [ẢNH CHỤP MÀN HÌNH: nút xuất Excel] -->

---

## 10. Yêu cầu xoá dữ liệu ứng viên

Nếu ứng viên yêu cầu xoá thông tin cá nhân (theo quy định bảo vệ dữ liệu), bạn cần:

1. Mở hồ sơ ứng viên.
2. Nhấn **Thao tác** → **Yêu cầu xoá dữ liệu**.
3. Nhập lý do và xác nhận.
4. Hệ thống sẽ ẩn danh hoá toàn bộ thông tin trong vòng 24 giờ và ghi lại trong audit log.

> ⚠️ Hành động này **không thể hoàn tác**. Vui lòng xác nhận kỹ trước khi thực hiện.

---

## 11. Câu hỏi thường gặp

**Hỏi: CV đã tải lên nhưng chưa thấy đánh giá AI?**
Đáp: Hệ thống cần 1–3 phút xử lý mỗi CV. Nếu sau 10 phút vẫn chưa có, liên hệ quản trị viên.

**Hỏi: AI đánh giá sai, phải làm gì?**
Đáp: Nhấn **Không đồng ý** trên hồ sơ ứng viên và ghi rõ lý do. Bạn vẫn có thể tiến hành phỏng vấn theo đánh giá của mình – AI chỉ hỗ trợ, không quyết định thay bạn.

**Hỏi: Có thể tải lên CV tiếng Anh không?**
Đáp: Có, hệ thống hỗ trợ cả tiếng Việt và tiếng Anh.

**Hỏi: Thông tin cá nhân của ứng viên có được bảo mật không?**
Đáp: Có. Trước khi gửi cho AI đánh giá, hệ thống tự động che tên, ảnh, số điện thoại và địa chỉ. Dữ liệu được lưu trữ theo quy định pháp luật hiện hành.

**Hỏi: Làm sao đổi mật khẩu?**
Đáp: Nhấn vào ảnh đại diện góc phải trên → **Cài đặt tài khoản** → **Đổi mật khẩu**.

**Hỏi: Hệ thống có nhận CV qua email không?**
Đáp: Có thể (nếu được bật). Liên hệ quản trị viên để biết địa chỉ email nhận CV và cách cấu hình.

---

*Phiên bản tài liệu: 1.0 · Cập nhật: 2026-11-10*
*Liên hệ hỗ trợ kỹ thuật: quản trị viên hệ thống của đơn vị bạn.*
