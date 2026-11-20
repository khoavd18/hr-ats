"""Add template and message storage; seed five immutable starter definitions."""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_email_templates"
down_revision: str | None = "0005_recruitment_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen migration data: independent of future application seed edits.
DEFAULTS = [
    {
        "key": "cv_received",
        "name": "Xác nhận đã nhận CV",
        "stage": None,
        "subject": "Đã nhận hồ sơ ứng tuyển {{ job_title }}",
        "body": "Chào {{ candidate_name }},\n"
        "\n"
        "{{ company_name }} đã nhận hồ sơ của bạn cho vị trí **{{ job_title }}**. Cảm "
        "ơn bạn đã quan tâm.\n"
        "\n"
        "Chúng tôi xử lý thông tin trong hồ sơ để xem xét tuyển dụng và chỉ chia sẻ "
        "với người có trách\n"
        "nhiệm. Hồ sơ được lưu theo chính sách lưu trữ của công ty. Thông báo này "
        "không thay thế bằng\n"
        "chứng đồng ý xử lý dữ liệu cá nhân của bạn.\n"
        "\n"
        "Để yêu cầu xoá hồ sơ hoặc hỏi về việc xử lý dữ liệu, vui lòng trả lời email "
        "này hoặc liên hệ {{\n"
        "recruiter_email }}.\n"
        "\n"
        "Trân trọng,\n"
        "{{ recruiter_name }}",
        "requires_confirmation": False,
    },
    {
        "key": "interview_invite",
        "name": "Mời phỏng vấn",
        "stage": "interview",
        "subject": "Mời phỏng vấn vị trí {{ job_title }}",
        "body": "Chào {{ candidate_name }},\n"
        "\n"
        "Chúng tôi mời bạn phỏng vấn vị trí **{{ job_title }}** tại {{ "
        "hiring_unit_name }}.\n"
        "\n"
        "- Thời gian: {{ interview_time }}\n"
        "- Địa điểm hoặc đường dẫn: {{ interview_location }}\n"
        "- Đầu mối phỏng vấn: {{ recruiter_name }} ({{ recruiter_email }})\n"
        "\n"
        "Vui lòng trả lời email để xác nhận tham dự. Chúng tôi sẽ cung cấp thông tin "
        "người phỏng vấn và\n"
        "tệp lịch khi xác nhận lịch hẹn.\n"
        "\n"
        "Trân trọng,\n"
        "{{ recruiter_name }}",
        "requires_confirmation": True,
    },
    {
        "key": "rejection",
        "name": "Thông báo kết quả tuyển dụng",
        "stage": "rejected",
        "subject": "Kết quả ứng tuyển vị trí {{ job_title }}",
        "body": "Chào {{ candidate_name }},\n"
        "\n"
        "Cảm ơn bạn đã dành thời gian ứng tuyển vị trí **{{ job_title }}**. Rất tiếc, "
        "lần này chúng tôi\n"
        "chưa thể tiếp tục cùng bạn.\n"
        "\n"
        "Nếu bạn đồng ý, chúng tôi mong được lưu hồ sơ cho cơ hội phù hợp trong tương "
        "lai, theo chính\n"
        "sách lưu trữ. Bạn có thể yêu cầu xoá hồ sơ qua {{ recruiter_email }}.\n"
        "\n"
        "Chúc bạn nhiều thành công.\n"
        "\n"
        "Trân trọng,\n"
        "{{ recruiter_name }}",
        "requires_confirmation": True,
    },
    {
        "key": "offer",
        "name": "Thư mời nhận việc",
        "stage": "offer",
        "subject": "Thư mời nhận việc vị trí {{ job_title }}",
        "body": "Chào {{ candidate_name }},\n"
        "\n"
        "{{ hiring_unit_name }} trân trọng mời bạn nhận vị trí **{{ job_title }}**.\n"
        "\n"
        "- Mức lương: {{ offer_salary }}\n"
        "- Ngày bắt đầu dự kiến: {{ offer_start_date }}\n"
        "\n"
        "Vui lòng phản hồi theo thời hạn đã thống nhất với người phụ trách tuyển dụng. "
        "Mọi câu hỏi xin\n"
        "liên hệ {{ recruiter_email }}.\n"
        "\n"
        "Trân trọng,\n"
        "{{ recruiter_name }}",
        "requires_confirmation": True,
    },
    {
        "key": "submitted_to_unit",
        "name": "Giới thiệu ứng viên đến đơn vị tuyển",
        "stage": "submitted",
        "subject": "Giới thiệu ứng viên cho vị trí {{ job_title }}",
        "body": "Kính gửi {{ hiring_unit_name }},\n"
        "\n"
        "Chúng tôi xin giới thiệu ứng viên **{{ candidate_name }}** cho vị trí **{{ "
        "job_title }}**. Vui\n"
        "lòng xem hồ sơ trong hệ thống tuyển dụng và phản hồi để chúng tôi phối hợp "
        "bước tiếp theo.\n"
        "\n"
        "Trân trọng,\n"
        "{{ recruiter_name }}\n"
        "{{ recruiter_email }}",
        "requires_confirmation": True,
    },
]


def record_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    stage = postgresql.ENUM(
        "new",
        "screening",
        "submitted",
        "interview",
        "offer",
        "hired",
        "rejected",
        "withdrawn",
        name="application_stage",
        create_type=False,
    )
    status = postgresql.ENUM(
        "draft", "queued", "sent", "failed", "cancelled", name="email_status", create_type=False
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "email_templates",
        *record_columns(),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("stage", stage),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "requires_confirmation", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.CheckConstraint(
            "requires_confirmation OR key = 'cv_received'", name="ck_email_templates_confirmation"
        ),
    )
    op.create_table(
        "email_messages",
        *record_columns(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id")),
        sa.Column("template_id", sa.Uuid(), sa.ForeignKey("email_templates.id")),
        sa.Column("to_email", sa.String(254), nullable=False),
        sa.Column("cc", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column(
            "status", status, server_default=sa.text("'draft'::email_status"), nullable=False
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_id", sa.Text()),
        sa.CheckConstraint("jsonb_typeof(cc) = 'array'", name="ck_email_messages_cc"),
    )
    for column in ("application_id", "template_id", "created_by"):
        op.create_index("ix_email_messages_" + column, "email_messages", [column])
    table = sa.table(
        "email_templates",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("stage", stage),
        sa.column("subject", sa.String()),
        sa.column("body", sa.Text()),
        sa.column("requires_confirmation", sa.Boolean()),
    )
    op.bulk_insert(table, [dict(id=uuid4(), **item) for item in DEFAULTS])


def downgrade() -> None:
    # Destructive rollback is tested only on disposable fixture databases.
    op.drop_table("email_messages")
    op.drop_table("email_templates")
    postgresql.ENUM(name="email_status").drop(op.get_bind(), checkfirst=True)
