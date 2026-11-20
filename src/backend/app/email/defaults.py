"""Polite Vietnamese starter templates; no real candidate or contact information."""

from typing import Any

DEFAULT_TEMPLATES: list[dict[str, Any]] = [
    dict(
        key="cv_received",
        name="Xác nhận đã nhận CV",
        stage=None,
        subject="Đã nhận hồ sơ ứng tuyển {{ job_title }}",
        body="""Chào {{ candidate_name }},

{{ company_name }} đã nhận hồ sơ của bạn cho vị trí **{{ job_title }}**. Cảm ơn bạn đã quan tâm.

Chúng tôi xử lý thông tin trong hồ sơ để xem xét tuyển dụng và chỉ chia sẻ với người có trách
nhiệm. Hồ sơ được lưu theo chính sách lưu trữ của công ty. Thông báo này không thay thế bằng
chứng đồng ý xử lý dữ liệu cá nhân của bạn.

Để yêu cầu xoá hồ sơ hoặc hỏi về việc xử lý dữ liệu, vui lòng trả lời email này hoặc liên hệ {{
recruiter_email }}.

Trân trọng,
{{ recruiter_name }}""",
        requires_confirmation=False,
    ),
    dict(
        key="interview_invite",
        name="Mời phỏng vấn",
        stage="interview",
        subject="Mời phỏng vấn vị trí {{ job_title }}",
        body="""Chào {{ candidate_name }},

Chúng tôi mời bạn phỏng vấn vị trí **{{ job_title }}** tại {{ hiring_unit_name }}.

- Thời gian: {{ interview_time }}
- Địa điểm hoặc đường dẫn: {{ interview_location }}
- Đầu mối phỏng vấn: {{ recruiter_name }} ({{ recruiter_email }})

Vui lòng trả lời email để xác nhận tham dự. Chúng tôi sẽ cung cấp thông tin người phỏng vấn và
tệp lịch khi xác nhận lịch hẹn.

Trân trọng,
{{ recruiter_name }}""",
        requires_confirmation=True,
    ),
    dict(
        key="rejection",
        name="Thông báo kết quả tuyển dụng",
        stage="rejected",
        subject="Kết quả ứng tuyển vị trí {{ job_title }}",
        body="""Chào {{ candidate_name }},

Cảm ơn bạn đã dành thời gian ứng tuyển vị trí **{{ job_title }}**. Rất tiếc, lần này chúng tôi
chưa thể tiếp tục cùng bạn.

Nếu bạn đồng ý, chúng tôi mong được lưu hồ sơ cho cơ hội phù hợp trong tương lai, theo chính
sách lưu trữ. Bạn có thể yêu cầu xoá hồ sơ qua {{ recruiter_email }}.

Chúc bạn nhiều thành công.

Trân trọng,
{{ recruiter_name }}""",
        requires_confirmation=True,
    ),
    dict(
        key="offer",
        name="Thư mời nhận việc",
        stage="offer",
        subject="Thư mời nhận việc vị trí {{ job_title }}",
        body="""Chào {{ candidate_name }},

{{ hiring_unit_name }} trân trọng mời bạn nhận vị trí **{{ job_title }}**.

- Mức lương: {{ offer_salary }}
- Ngày bắt đầu dự kiến: {{ offer_start_date }}

Vui lòng phản hồi theo thời hạn đã thống nhất với người phụ trách tuyển dụng. Mọi câu hỏi xin
liên hệ {{ recruiter_email }}.

Trân trọng,
{{ recruiter_name }}""",
        requires_confirmation=True,
    ),
    dict(
        key="submitted_to_unit",
        name="Giới thiệu ứng viên đến đơn vị tuyển",
        stage="submitted",
        subject="Giới thiệu ứng viên cho vị trí {{ job_title }}",
        body="""Kính gửi {{ hiring_unit_name }},

Chúng tôi xin giới thiệu ứng viên **{{ candidate_name }}** cho vị trí **{{ job_title }}**. Vui
lòng xem hồ sơ trong hệ thống tuyển dụng và phản hồi để chúng tôi phối hợp bước tiếp theo.

Trân trọng,
{{ recruiter_name }}
{{ recruiter_email }}""",
        requires_confirmation=True,
    ),
]
