"""T15: profile access, human feedback and notes within the authorized Job."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import authorize
from app.models.activity import Activity, AuditLog
from app.models.applications import AiFeedback, Application
from app.models.candidates import CvFile
from app.models.enums import ActivityType
from app.models.users import User
from app.schemas.core import ActivityRead, AiFeedbackRead, ApplicationRead, CandidateRead
from app.schemas.profile import (
    ApplicationDetail,
    CandidatePatch,
    FeedbackInput,
    ProfileActivity,
    ProfileFile,
)
from app.services.activity import log_activity
from app.services.applications import accessible_job, eligible_candidate

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def accessible_application(session: Session, actor: User, application_id: UUID) -> Application:
    application = session.scalar(
        select(Application).where(
            Application.id == application_id, Application.deleted_at.is_(None)
        )
    )
    if application is None:
        raise AppError("NOT_FOUND", "Không tìm thấy hồ sơ ứng tuyển.", 404)
    accessible_job(session, actor, application.job_id)
    eligible_candidate(session, application.candidate_id)
    return application


def detail(
    session: Session, actor: User, application_id: UUID, ip: str | None
) -> ApplicationDetail:
    application = accessible_application(session, actor, application_id)
    candidate = eligible_candidate(session, application.candidate_id)
    files = list(
        session.scalars(
            select(CvFile)
            .where(CvFile.candidate_id == candidate.id, CvFile.deleted_at.is_(None))
            .order_by(CvFile.created_at.desc(), CvFile.id)
        )
    )
    for file in files:
        authorize(actor, "cv_files.view", file, session=session)
    activities = session.execute(
        select(Activity, User.full_name)
        .outerjoin(User, User.id == Activity.actor_id)
        .where(Activity.application_id == application.id, Activity.deleted_at.is_(None))
        .order_by(Activity.occurred_at.desc(), Activity.id)
    ).all()
    feedback = session.scalar(
        select(AiFeedback).where(
            AiFeedback.application_id == application.id,
            AiFeedback.user_id == actor.id,
            AiFeedback.deleted_at.is_(None),
        )
    )
    snapshot = ApplicationDetail(
        application=ApplicationRead.model_validate(application),
        candidate=CandidateRead.model_validate(candidate),
        cv_files=[
            ProfileFile(
                id=f.id,
                mime_type=f.mime_type,
                status=f.status,
                extracted_text=f.extracted_text if f.mime_type == DOCX else None,
            )
            for f in files
        ],
        feedback=AiFeedbackRead.model_validate(feedback) if feedback else None,
        activities=[
            ProfileActivity(**ActivityRead.model_validate(a).model_dump(), actor_name=name)
            for a, name in activities
        ],
        loaded_at=datetime.now(UTC),
    )
    # candidate.view uses the same action/entity convention as cv_file.view T07.
    session.add(
        AuditLog(
            actor_id=actor.id, action="view", entity="candidate", entity_id=candidate.id, ip=ip
        )
    )
    session.commit()
    return snapshot


def feedback(
    session: Session, actor: User, application_id: UUID, body: FeedbackInput
) -> AiFeedbackRead:
    application = accessible_application(session, actor, application_id)
    values = body.model_dump()
    # Atomic upsert also handles concurrent submissions from two browser tabs.
    with session.begin_nested():
        row = session.scalars(
            insert(AiFeedback)
            .values(application_id=application.id, user_id=actor.id, **values)
            .on_conflict_do_update(
                constraint="uq_ai_feedback_application_user",
                set_={**values, "updated_at": func.now(), "deleted_at": None},
            )
            .returning(AiFeedback),
            execution_options={"populate_existing": True},
        ).one()
        log_activity(
            session,
            type=ActivityType.ai_feedback,
            actor_id=actor.id,
            job_id=application.job_id,
            application_id=application.id,
            candidate_id=application.candidate_id,
            payload={"verdict": body.verdict, "corrected_level": body.corrected_level},
        )
        snapshot = AiFeedbackRead.model_validate(row)
    session.commit()
    return snapshot


def add_note(session: Session, actor: User, application_id: UUID, text: str) -> ProfileActivity:
    application = accessible_application(session, actor, application_id)
    # Deliberate user-authored content, stored only in the authorized application.
    # The shared metadata logger continues rejecting free text and CV contents.
    activity = Activity(
        type=ActivityType.note,
        actor_id=actor.id,
        job_id=application.job_id,
        application_id=application.id,
        candidate_id=application.candidate_id,
        payload={"text": text},
    )
    session.add(activity)
    session.flush()
    snapshot = ProfileActivity(
        **ActivityRead.model_validate(activity).model_dump(), actor_name=actor.full_name
    )
    session.commit()
    return snapshot


def patch_candidate(
    session: Session, actor: User, candidate_id: UUID, body: CandidatePatch
) -> CandidateRead:
    candidate = eligible_candidate(session, candidate_id)
    authorize(actor, "job_candidates.view", candidate, session=session)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(candidate, key, value)
    session.flush()
    snapshot = CandidateRead.model_validate(candidate)
    session.commit()
    return snapshot
