# KPI tuyển dụng (nháp)

status: draft. Người duyệt: UNKNOWN. Phiên bản triển khai: T26/v1.
VERIFIED chỉ có nghĩa truy vấn khớp fixture tính tay, **không** có nghĩa định
nghĩa đã được nghiệp vụ duyệt. Chưa có KPI `status: approved`.

Nguồn công thức: `docs/specs/06-email-reports.md`, mục KPI và contract T26.
Mục đích: hỗ trợ HR xem lượng công việc, tiến độ tuyển và phản hồi AI; chưa
dùng các số nháp này để tự động đánh giá/xếp loại nhân viên. Không đặt target,
trọng số hay ngưỡng. Khi duyệt dùng mẫu
`.agents/skills/kpi-metrics-engineer/references/metric-contract-template.md`.

| KPI | Định nghĩa nháp / đơn vị | Xem theo | Hàm trong code |
|---|---|---|---|
| CV mới nhận | Đếm file tạo trong kỳ, không phải số người duy nhất | Ngày/tuần, người upload hoặc owner Job | `app.reports.queries.new_cvs` |
| CV đã screen | Đếm sự kiện từ new sang bước khác, gồm loại/đi lại/hoàn tác | Kỳ, owner Application | `app.reports.queries.screened` |
| CV gửi đơn vị tuyển | Đếm sự kiện vào submitted, gồm lượt vào lại | Kỳ, owner Application/Job/đơn vị | `app.reports.queries.submitted` |
| Phỏng vấn | Đếm lịch theo scheduled_at; đã đến giờ / sắp tới | Kỳ, owner Application | `app.reports.queries.interviews` |
| Offer | Đếm offer có sent_at trong kỳ | Kỳ, owner Application | `app.reports.queries.offers` |
| Nhận việc | Đếm placement theo created_at, không theo start_date | Kỳ, owner Application | `app.reports.queries.placements` |
| Tỉ lệ chuyển đổi | Hồ sơ từng vào bước kế / hồ sơ từng vào bước hiện tại trong kỳ; distinct theo từng bước | Job/recruiter/đơn vị | `app.reports.queries.stage_conversion` |
| Time-to-fill | Trung vị số ngày thực từ opened_at đến created_at của placement trong kỳ | Job/recruiter/đơn vị | `app.reports.queries.time_to_fill` |
| Thời gian ở stage | Trung vị ngày của lượt ở bước đã kết thúc trong kỳ | Bước/Job/recruiter/đơn vị | `app.reports.queries.stage_duration` |
| Job đang mở và trễ hạn | Snapshot Job open, deadline < hôm nay Việt Nam, placement < headcount | Owner Job | `app.reports.queries.overdue_jobs` |
| Doanh thu placement | Tổng fee_amount đã biết, VND; kèm số có/chưa có phí | Kỳ tạo placement, owner Application | `app.reports.queries.placement_revenue` |
| Đồng thuận AI | agree / (agree + disagree), kèm hai số đếm; không phải đo độ chính xác AI bằng nhãn chuẩn | Kỳ tạo feedback, owner Application | `app.reports.queries.ai_agreement` |
| Hoạt động | Đếm activity theo loại và actor_id; null actor là hệ thống | Kỳ, người thực hiện | `app.reports.queries.activities` |

Các hàm nhận `(session, start, end, filters)`; start/end là UTC chuyển từ ngày
Việt Nam `[from, to)`. Kết quả map khóa `None` khi tổng hợp; `grouped=True`
nhóm theo ID người phụ trách (None lúc này là chưa gán/hệ thống). CV theo ngày
dùng `new_cvs_by_day`, thêm ngày rỗng bằng 0. Nhóm team phải tính lại distinct,
trung vị và tử/mẫu; không cộng tỉ lệ, không lấy trung bình tỉ lệ/trung vị cá nhân.

Không có sự kiện → count=0. Không có mẫu/mẫu số=0 → median/rate=null.
Không có phí đã biết → amount=null; phí xác nhận bằng 0 vẫn là 0. Tổng phí khi
có mẫu thiếu là tổng phần đã biết và luôn kèm missing_count, không mặc định
phí thiếu là 0. Job trễ hạn là snapshot, không cộng qua các ngày.

ASSUMED: attribution, lịch sử thiếu mốc đầu, kỳ của feedback/upsert, dữ liệu
soft delete, snapshot và tỉ lệ flow chưa được người dùng duyệt; chi tiết tại
spec 06 và `docs/specs/open-questions.md` #94–#99. Không có KPI theo lý do loại
trong T26; chuẩn hoá mã lý do theo nhắc việc T20 vẫn cần trước khi bổ sung KPI đó.
