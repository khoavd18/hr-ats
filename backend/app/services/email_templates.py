from datetime import datetime
from email.utils import parseaddr
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.permissions import authorize
from app.email.defaults import DEFAULT_TEMPLATES
from app.email.render import render_email, validate_template
from app.models import (
    Application,
    Candidate,
    EmailTemplate,
    HiringUnit,
    Interview,
    Job,
    Offer,
    User,
)
from app.schemas.email import (
    PreviewChoice,
    PreviewChoices,
    PreviewInput,
    PreviewRead,
    TemplateCreate,
    TemplateList,
    TemplatePatch,
    TemplateRead,
)
from app.services.applications import eligible_candidate
from app.services.profile import accessible_application


def seed_templates(session: Session) -> None:
    """Insert missing defaults only; never overwrite an HR edit or inactive template."""
    for item in DEFAULT_TEMPLATES:
        session.execute(
            insert(EmailTemplate)
            .values(id=uuid4(), **item)
            .on_conflict_do_nothing(index_elements=["key"])
        )
    session.flush()


def list_templates(session: Session, actor: User, page: int, page_size: int) -> TemplateList:
    authorize(actor, "email_templates.manage")
    rows = session.scalars(
        select(EmailTemplate)
        .order_by(EmailTemplate.created_at, EmailTemplate.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return TemplateList(
        items=[TemplateRead.model_validate(row) for row in rows],
        total=session.scalar(select(func.count()).select_from(EmailTemplate)) or 0,
    )


def get_template(
    session: Session, actor: User, template_id: UUID, *, lock: bool = False
) -> EmailTemplate:
    authorize(actor, "email_templates.manage")
    query = select(EmailTemplate).where(EmailTemplate.id == template_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = session.scalar(query)
    if row is None:
        raise AppError("NOT_FOUND", "Không tìm thấy mẫu email.", 404)
    return row


def save_template(
    session: Session,
    actor: User,
    data: TemplateCreate | TemplatePatch,
    template_id: UUID | None = None,
) -> EmailTemplate:
    authorize(actor, "email_templates.manage")
    row = get_template(session, actor, template_id, lock=True) if template_id else EmailTemplate()
    values = data.model_dump(exclude_unset=template_id is not None)
    if template_id:
        effective = {key: getattr(row, key) for key in TemplateCreate.model_fields} | values
        try:
            TemplateCreate.model_validate(effective)
        except ValidationError:
            raise AppError("VALIDATION_ERROR", "Dữ liệu không hợp lệ.", 422) from None
    else:
        effective = values
    validate_template(effective["subject"])
    validate_template(effective["body"])
    try:
        with session.begin_nested():
            for key, value in values.items():
                setattr(row, key, value)
            session.add(row)
            session.flush()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise AppError("EMAIL_TEMPLATE_EXISTS", "Mã mẫu email đã được sử dụng.", 409) from None
        raise
    return row


def build_context(
    session: Session, actor: User, application_id: UUID, settings: Settings
) -> dict[str, str]:
    application = accessible_application(session, actor, application_id)
    candidate = eligible_candidate(session, application.candidate_id)
    job = session.get(Job, application.job_id)
    assert job is not None
    unit = session.get(HiringUnit, job.hiring_unit_id)
    recruiter = session.get(User, application.owner_id)
    context = {"candidate_name": candidate.full_name, "job_title": job.title}
    if unit:
        context["hiring_unit_name"] = unit.name
    if recruiter:
        context.update(recruiter_name=recruiter.full_name, recruiter_email=recruiter.email)
    company_name, _ = parseaddr(settings.smtp_from)
    if company_name.strip():
        context["company_name"] = company_name
    interview = session.scalar(
        select(Interview)
        .where(Interview.application_id == application.id, Interview.deleted_at.is_(None))
        .order_by(Interview.scheduled_at.desc(), Interview.id)
        .limit(1)
    )
    if interview:
        context["interview_time"] = interview.scheduled_at.astimezone(
            ZoneInfo(settings.tz)
        ).strftime("%d/%m/%Y %H:%M")
        if interview.location_or_link:
            context["interview_location"] = interview.location_or_link
    offer = session.scalar(
        select(Offer)
        .where(Offer.application_id == application.id, Offer.deleted_at.is_(None))
        .order_by(Offer.created_at.desc(), Offer.id)
        .limit(1)
    )
    if offer:
        if offer.salary is not None:
            context["offer_salary"] = f"{offer.salary:,}".replace(",", ".") + " đồng"
        if offer.start_date:
            context["offer_start_date"] = offer.start_date.strftime("%d/%m/%Y")
    return context


def preview(
    session: Session, actor: User, template_id: UUID, data: PreviewInput, settings: Settings
) -> PreviewRead:
    row = get_template(session, actor, template_id)
    rendered = render_email(
        data.subject if data.subject is not None else row.subject,
        data.body if data.body is not None else row.body,
        build_context(session, actor, data.application_id, settings),
    )
    return PreviewRead(subject=rendered.subject, body=rendered.body, body_html=rendered.body_html)


def preview_choices(
    session: Session, actor: User, page: int, page_size: int, q: str
) -> PreviewChoices:
    authorize(actor, "email_templates.manage")
    # Only privileged template editors can enumerate this minimal application selector.
    today = datetime.now(ZoneInfo(get_settings().tz)).date()
    query = (
        select(Application.id, Candidate.full_name, Job.title)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(
            Application.deleted_at.is_(None),
            Candidate.deleted_at.is_(None),
            Candidate.merged_into_id.is_(None),
            Candidate.retention_until >= today,
        )
    )
    if q.strip():
        query = query.where(
            or_(
                Candidate.full_name.icontains(q.strip(), autoescape=True),
                Job.title.icontains(q.strip(), autoescape=True),
            )
        )
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.execute(
        query.order_by(Candidate.full_name, Application.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return PreviewChoices(
        items=[PreviewChoice(id=row[0], candidate_name=row[1], job_title=row[2]) for row in rows],
        total=total,
    )
