"""T05 integration tests; all names, contacts and document metadata are synthetic."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.core.errors import AppError
from app.core.permissions import authorize
from app.models import (
    Activity,
    AiFeedback,
    Application,
    AuditLog,
    Candidate,
    CvFile,
    HiringUnit,
    Job,
    JobMember,
    StageEvent,
    User,
    UserRole,
)
from app.models.enums import (
    ActivityType,
    ApplicationStage,
    CandidateSource,
    HiringUnitKind,
    ProcessingStatus,
)
from app.schemas.core import (
    ActivityRead,
    AiFeedbackRead,
    ApplicationRead,
    AuditLogRead,
    CandidateRead,
    CvFileRead,
    HiringUnitRead,
    JobMemberRead,
    JobRead,
    StageEventRead,
)
from app.services.activity import log_activity


@pytest.fixture
def records(db_session: Session, account: User) -> SimpleNamespace:
    member = User(
        email="member@example.invalid",
        full_name="Thành viên giả",
        role=UserRole.recruiter,
        password_hash="unused-synthetic-hash",
    )
    outsider = User(
        email="outsider@example.invalid",
        full_name="Tài khoản ngoài giả",
        role=UserRole.recruiter,
        password_hash="unused-synthetic-hash",
    )
    unit = HiringUnit(name="Đơn vị giả", kind=HiringUnitKind.department)
    candidate = Candidate(
        full_name="Nguyễn Ứng Viên Giả",
        current_title="Kỹ sư dữ liệu",
        skills=["Phân tích", "Python"],
        retention_until=date(2028, 11, 8),
    )
    db_session.add_all([member, outsider, unit, candidate])
    db_session.flush()
    job = Job(
        hiring_unit_id=unit.id, title="Vị trí giả", description="Mô tả giả", owner_id=account.id
    )
    db_session.add(job)
    db_session.flush()
    membership = JobMember(job_id=job.id, user_id=member.id)
    application = Application(candidate_id=candidate.id, job_id=job.id, owner_id=account.id)
    cv = CvFile(
        candidate_id=candidate.id,
        storage_key="synthetic/" + uuid4().hex,
        original_filename="synthetic.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        sha256="a" * 64,
        uploaded_by=account.id,
        job_id=job.id,
    )
    db_session.add_all([membership, application, cv])
    db_session.flush()
    event = StageEvent(
        application_id=application.id, to_stage=ApplicationStage.new, actor_id=account.id
    )
    feedback = AiFeedback(application_id=application.id, user_id=account.id, verdict="agree")
    audit = AuditLog(
        actor_id=account.id,
        action="candidate.view",
        entity="candidate",
        entity_id=candidate.id,
        ip="127.0.0.1",
    )
    db_session.add_all([event, feedback, audit])
    activity = log_activity(
        db_session,
        type=ActivityType.cv_uploaded,
        actor_id=account.id,
        job_id=job.id,
        application_id=application.id,
        candidate_id=candidate.id,
        payload={"cv_file_id": str(cv.id)},
    )
    return SimpleNamespace(
        owner=account,
        member=member,
        outsider=outsider,
        unit=unit,
        candidate=candidate,
        job=job,
        membership=membership,
        application=application,
        cv=cv,
        event=event,
        feedback=feedback,
        audit=audit,
        activity=activity,
    )


def test_create_every_core_table_and_serialize_read_contracts(db_session, records):
    pairs = [
        (records.unit, HiringUnitRead),
        (records.job, JobRead),
        (records.membership, JobMemberRead),
        (records.candidate, CandidateRead),
        (records.cv, CvFileRead),
        (records.application, ApplicationRead),
        (records.event, StageEventRead),
        (records.feedback, AiFeedbackRead),
        (records.audit, AuditLogRead),
        (records.activity, ActivityRead),
    ]
    db_session.commit()
    for row, schema in pairs:
        db_session.refresh(row)
        assert row.id.version == 4
        assert row.created_at.utcoffset().total_seconds() == 0
        assert row.updated_at is not None
        assert schema.model_validate(row).model_dump(mode="json")["id"] == str(row.id)
    assert records.application.stage == ApplicationStage.new
    assert records.application.ai_status == ProcessingStatus.pending
    assert records.application.ai_level is None
    assert records.application.ai_score is None
    assert records.candidate.consent_at is None
    assert records.candidate.source == CandidateSource.upload
    for row, schema in [
        (records.candidate, CandidateRead),
        (records.cv, CvFileRead),
        (records.job, JobRead),
    ]:
        data = schema.model_validate(row).model_dump()
        assert (
            not {
                "embedding",
                "anonymized_text",
                "search_tsv",
                "extracted_text",
                "parsed_json",
                "storage_key",
                "error",
            }
            & data.keys()
        )


def test_application_uniqueness_is_only_for_active_rows(db_session, records):
    def duplicate():
        return Application(
            candidate_id=records.candidate.id, job_id=records.job.id, owner_id=records.owner.id
        )

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(duplicate())
        db_session.flush()
    records.application.deleted_at = datetime.now(UTC)
    db_session.flush()
    replacement = duplicate()
    db_session.add(replacement)
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        records.application.deleted_at = None
        db_session.flush()
    assert db_session.scalar(select(func.count()).select_from(Application)) == 2


@pytest.mark.parametrize("kind", ["membership", "feedback", "hash", "foreign_key"])
def test_core_constraints_reject_duplicates_and_missing_references(db_session, records, kind):
    row = {
        "membership": lambda: JobMember(job_id=records.job.id, user_id=records.member.id),
        "feedback": lambda: AiFeedback(
            application_id=records.application.id, user_id=records.owner.id, verdict="disagree"
        ),
        "hash": lambda: CvFile(
            storage_key="synthetic",
            original_filename="synthetic.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            sha256="a" * 64,
        ),
        "foreign_key": lambda: JobMember(job_id=uuid4(), user_id=records.member.id),
    }[kind]()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(row)
        db_session.flush()


@pytest.mark.parametrize(("field", "value"), [("ai_score", -1), ("ai_score", 101)])
def test_ai_score_range_is_enforced(db_session, records, field, value):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        setattr(records.application, field, value)
        db_session.flush()


def test_candidate_email_requires_lowercase_and_import_enum_uses_value(db_session, records):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        records.candidate.email = "FAKE@example.invalid"
        db_session.flush()
    records.candidate.source = CandidateSource.import_
    records.candidate.email = "fake@example.invalid"
    db_session.flush()
    db_session.refresh(records.candidate)
    assert records.candidate.source == CandidateSource.import_
    assert db_session.scalar(text("SELECT source::text FROM candidates")) == "import"


def search_ids(session, query):
    return session.scalars(
        select(Candidate.id).where(
            Candidate.search_tsv.op("@@")(func.plainto_tsquery("simple", func.unaccent(query))),
            Candidate.deleted_at.is_(None),
        )
    ).all()


def test_full_text_is_accent_insensitive_and_trigger_refreshes_all_sources(db_session, records):
    for query in ["nguyen", "NGUYỄN", "ky su", "phan tich", "python"]:
        assert search_ids(db_session, query) == [records.candidate.id]
    assert search_ids(db_session, "missing-token") == []
    records.candidate.full_name = "Trần Ứng Viên Giả"
    records.candidate.current_title = None
    records.candidate.skills = ["Thiết kế"]
    db_session.flush()
    assert search_ids(db_session, "nguyen") == []
    assert search_ids(db_session, "python") == []
    assert search_ids(db_session, "ky su") == []
    assert search_ids(db_session, "tran thiet ke") == [records.candidate.id]
    db_session.execute(text("UPDATE candidates SET search_tsv = ''::tsvector"))
    assert search_ids(db_session, "tran") == [records.candidate.id]
    db_session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = (
        db_session.execute(
            text(
                "EXPLAIN SELECT id FROM candidates WHERE search_tsv @@ "
                "plainto_tsquery('simple', unaccent('tran'))"
            )
        )
        .scalars()
        .all()
    )
    assert "ix_candidates_search_tsv" in " ".join(plan)


def test_vector_cosine_top_k_and_indexes_use_configured_dimension(db_session, records):
    dim = get_settings().embedding_dim
    query_vector = [1.0] + [0.0] * (dim - 1)
    records.candidate.embedding = query_vector
    middle = Candidate(
        full_name="Ứng viên giả B",
        retention_until=date(2028, 1, 1),
        embedding=[1.0, 1.0] + [0.0] * (dim - 2),
    )
    far = Candidate(
        full_name="Ứng viên giả C",
        retention_until=date(2028, 1, 1),
        embedding=[0.0, 1.0] + [0.0] * (dim - 2),
    )
    db_session.add_all([middle, far])
    records.job.embedding = query_vector
    db_session.flush()
    distance = Candidate.embedding.cosine_distance(query_vector)
    top = db_session.execute(
        select(Candidate.id, distance.label("distance"))
        .where(Candidate.embedding.is_not(None))
        .order_by(distance)
        .limit(2)
    ).all()
    assert [r.id for r in top] == [records.candidate.id, middle.id]
    assert top[0].distance == pytest.approx(0)
    assert 0 < top[1].distance < 1
    assert db_session.scalar(select(func.vector_dims(Job.embedding))) == dim
    db_session.execute(text("SET LOCAL enable_seqscan = off"))
    vector_literal = "[" + ",".join(str(v) for v in query_vector) + "]"
    plan = (
        db_session.execute(
            text(
                "EXPLAIN SELECT id FROM candidates "
                "ORDER BY embedding <=> CAST(:vector AS vector) LIMIT 2"
            ),
            {"vector": vector_literal},
        )
        .scalars()
        .all()
    )
    assert "ix_candidates_embedding" in " ".join(plan)
    with pytest.raises(StatementError), db_session.begin_nested():
        records.candidate.embedding = [1.0]
        db_session.flush()


@pytest.mark.parametrize("role", list(UserRole))
@pytest.mark.parametrize("relation", ["owner", "member", "outsider"])
@pytest.mark.parametrize(
    "action", ["jobs.view", "job_candidates.view", "applications.move", "emails.send"]
)
def test_job_permissions_are_resolved_from_database(db_session, records, role, relation, action):
    actor = getattr(records, relation)
    actor.role = role
    if role != UserRole.recruiter or relation != "outsider":
        authorize(actor, action, records.job, session=db_session)
    else:
        with pytest.raises(AppError) as error:
            authorize(actor, action, records.job, session=db_session)
        assert error.value.status == 403


@pytest.mark.parametrize("relation", ["owner", "member", "outsider"])
def test_candidate_and_application_access_requires_accessible_active_job(
    db_session, records, relation
):
    actor = getattr(records, relation)
    actor.role = UserRole.recruiter
    for resource, action in [
        (records.candidate, "job_candidates.view"),
        (records.application, "applications.move"),
        (records.application, "emails.send"),
    ]:
        if relation == "outsider":
            with pytest.raises(AppError):
                authorize(actor, action, resource, session=db_session)
        else:
            authorize(actor, action, resource, session=db_session)
    authorize(actor, "cv_bank.search")


def test_revoked_membership_and_soft_deleted_records_remove_access(db_session, records):
    actor = records.member
    authorize(actor, "jobs.view", records.job, session=db_session)
    db_session.delete(records.membership)
    db_session.flush()
    with pytest.raises(AppError):
        authorize(actor, "jobs.view", records.job, session=db_session)
    actor = records.owner
    actor.role = UserRole.recruiter
    for target in [records.application, records.candidate]:
        target.deleted_at = datetime.now(UTC)
        db_session.flush()
        for resource in [records.application, records.candidate]:
            with pytest.raises(AppError):
                authorize(actor, "job_candidates.view", resource, session=db_session)
        target.deleted_at = None
        db_session.flush()


def test_pending_owner_changes_and_application_owner_do_not_grant_job_access(db_session, records):
    actor = records.outsider
    records.job.owner_id = actor.id
    records.application.owner_id = actor.id
    for resource in [records.job, records.application, records.candidate]:
        with pytest.raises(AppError):
            authorize(actor, "job_candidates.view", resource, session=db_session)
    assert db_session.scalar(text("SELECT owner_id FROM jobs")) == records.owner.id
    db_session.expire(records.job)
    db_session.expire(records.application)
    with pytest.raises(AppError):
        authorize(actor, "jobs.view", records.job)  # DB resources require a session.
    with pytest.raises(AppError):
        authorize(records.member, "applications.move", records.candidate, session=db_session)


def test_activity_participates_in_caller_rollback_and_copies_payload(db_session):
    metadata = {"from_stage": "new", "to_stage": "screening", "attempt_count": 1}
    occurred = datetime(2026, 1, 1, tzinfo=UTC)
    with db_session.begin_nested() as savepoint:
        activity = log_activity(
            db_session, type=ActivityType.stage_changed, payload=metadata, occurred_at=occurred
        )
        activity_id = activity.id
        metadata["to_stage"] = "offer"
        assert activity.payload["to_stage"] == "screening"
        assert activity.actor_id is None
        assert activity.occurred_at == occurred
        savepoint.rollback()
    assert db_session.get(Activity, activity_id) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"cv_text": "Synthetic confidential text"},
        {"nested": [{"full_name": "Tên giả"}]},
        {"parsed_json": {}},
        {"note": "fake@example.invalid"},
        {"phone_number": "000000000"},
        {"file": object()},
    ],
)
def test_activity_rejects_sensitive_or_non_json_payload_without_echoing(db_session, payload):
    with pytest.raises(ValueError, match="non-sensitive JSON metadata only"):
        log_activity(db_session, type=ActivityType.note, payload=payload)
    assert db_session.scalar(select(func.count()).select_from(Activity)) == 0


def test_migration_reads_embedding_dim_for_both_vector_columns(empty_engine: Engine, monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIM", "8")
    get_settings.cache_clear()
    try:
        with empty_engine.begin() as connection:
            config = Config(str(REPO_ROOT / "backend/alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            types = (
                connection.execute(
                    text(
                        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                        "WHERE attname = 'embedding' AND attrelid IN "
                        "('candidates'::regclass, 'jobs'::regclass)"
                    )
                )
                .scalars()
                .all()
            )
            assert types == ["vector(8)", "vector(8)"]
            command.downgrade(config, "base")
    finally:
        get_settings.cache_clear()
