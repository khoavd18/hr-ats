# Workflow Telegram cho HR ATS

Các template dùng HTTPS của profile `automation`. Dùng cùng project n8n
cho các workflow và Data Table.

1. Khởi động profile theo [hướng dẫn triển khai](../../docs/deploy.md), rồi
   tạo owner trong n8n từ mạng quản trị.
2. Từ gốc repo, chạy `sh automation/n8n/import-workflows.sh` để import
   bản chưa publish. Chỉ chạy lại khi muốn thay template có cùng workflow
   ID. Xuất bản sao workflow đã chỉnh cục bộ trước khi import đè.
3. Tạo credential **HR ATS Webhook Signing**. Signing Key khớp
   `INTEGRATION_WEBHOOK_SECRET`. ATS Web Origin là origin của giao diện ATS,
   ví dụ `https://ats.example.com`.
4. Tạo Data Table `hr_ats_delivered_events` với cột `event_id` kiểu String.
   Chọn bảng đó ở **Find sent event** và **Record sent event**. Nếu cần ánh
   xạ lại cột ghi, dùng `{{ $("Verify HR ATS Event").first().json.event_id }}`.
5. Chọn Signing credential cho **Verify HR ATS Event** và chọn credential
   Telegram, Chat ID cho **Send Telegram**. Publish khi các cài đặt đã được
   kiểm tra. File JSON đặt sẵn path và không chứa credential.
6. Bật `INTEGRATION_WEBHOOKS_ENABLED` trên API, worker và Beat. Với W5, đặt
   `N8N_OVERDUE_USER_ID` theo tài khoản nhận nhắc và tắt cơ chế T34
   `N8N_OVERDUE_ENABLED` trước khi chuyển. Bật từng loại thông báo từ
   **Cài đặt → Tích hợp**.

Các lần retry ở ATS giữ nguyên ID. Workflow ghi ID sau khi Telegram xác
nhận gửi và trước ACK. Nếu n8n dừng giữa lúc nhận xác nhận Telegram và
lưu ID, lần gửi lại có thể tạo thêm một tin. Chỉ dùng bảng này cho các
lượt gửi của ATS. Tránh gửi song song thủ công cùng một ID.
