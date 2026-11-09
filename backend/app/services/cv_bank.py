"""Search summaries and explicit human merges. No raw CV data leaves this service."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, load_only

from app.ai.anonymize import anonymize
from app.ai.embed import EmbeddingError, get_embedder, validate_vectors
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.permissions import authorize
from app.models import DataRequest
from app.models.activity import Activity
from app.models.applications import Application
from app.models.candidates import Candidate, CvFile
from app.models.enums import ActivityType, CandidateSource
from app.models.users import User
from app.schemas.cv_bank import BankCandidate, CandidateBrief, CandidateList
from app.services.activity import log_activity
from app.services.applications import accessible_job, eligible_candidate


def eligible_filters():
    today = datetime.now(ZoneInfo(get_settings().tz)).date()
    return (
        Candidate.deleted_at.is_(None),
        Candidate.merged_into_id.is_(None),
        Candidate.retention_until >= today,
    )


def summaries_query():
    return (
        select(Candidate)
        .options(
            load_only(
                Candidate.id,
                Candidate.full_name,
                Candidate.current_title,
                Candidate.years_experience,
                Candidate.skills,
                Candidate.location,
                Candidate.source,
                Candidate.created_at,
            )
        )
        .where(*eligible_filters())
    )


def summaries(session: Session, candidates: list[Candidate]) -> list[BankCandidate]:
    if not candidates:
        return []
    ids = [c.id for c in candidates]
    hint = CvFile.parsed_json["possible_duplicate_of"].astext
    # Read only the generated hint, never load parsed_json or CV content.
    hints = session.execute(
        select(CvFile.candidate_id, hint)
        .where(
            CvFile.deleted_at.is_(None),
            hint.is_not(None),
            or_(CvFile.candidate_id.in_(ids), hint.in_([str(id) for id in ids])),
        )
        .order_by(CvFile.created_at.desc(), CvFile.id)
    ).all()
    pairs: list[tuple[UUID, UUID]] = []
    for source, raw_target in hints:
        try:
            target = UUID(raw_target)
        except (ValueError, TypeError):
            continue
        if source is not None and source != target:
            pairs.append((source, target))
    related_ids = {id for pair in pairs for id in pair}
    related = (
        {
            c.id: CandidateBrief.model_validate(c)
            for c in session.scalars(summaries_query().where(Candidate.id.in_(related_ids)))
        }
        if related_ids
        else {}
    )
    duplicates: dict[UUID, CandidateBrief] = {}
    for source, target in pairs:
        if source in related and target in related:
            duplicates.setdefault(source, related[target])
            duplicates.setdefault(target, related[source])
    return [
        BankCandidate(
            **CandidateBrief.model_validate(c).model_dump(),
            possible_duplicate=duplicates.get(c.id),
        )
        for c in candidates
    ]


def search(
    session: Session,
    actor: User,
    *,
    q: str = "",
    skills: str = "",
    min_years: Decimal | None = None,
    location: str = "",
    source: CandidateSource | None = None,
    page: int = 1,
    page_size: int = 20,
    semantic: bool = False,
    settings: Settings | None = None,
) -> CandidateList:
    authorize(actor, "cv_bank.search")
    query = summaries_query()
    if min_years is not None:
        query = query.where(Candidate.years_experience >= min_years)
    if location.strip():
        # Escape wildcard characters before binding; unaccent preserves the escape character.
        escaped = location.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            func.lower(func.unaccent(Candidate.location)).like(
                func.lower(func.unaccent(f"%{escaped}%")), escape="\\"
            )
        )
    if source is not None:
        query = query.where(Candidate.source == source)
    skill = func.jsonb_array_elements_text(Candidate.skills).column_valued("skill")
    for value in dict.fromkeys(s.strip() for s in skills.split(",") if s.strip()):
        query = query.where(
            select(1)
            .where(func.lower(func.unaccent(skill)) == func.lower(func.unaccent(value)))
            .exists()
        )
    q = q.strip()
    order = [Candidate.created_at.desc(), Candidate.id]
    if semantic:
        if not q:
            raise AppError("VALIDATION_ERROR", "Hãy nhập nội dung cần tìm.", 422)
        settings = settings or get_settings()
        # A query is a skill/title phrase, not a CV header; preserve those phrases
        # while removing contacts and labeled personal metadata locally.
        safe_query = anonymize("Tìm kiếm:\n" + q, None).removeprefix("Tìm kiếm:").strip()
        if not safe_query:
            raise AppError("VALIDATION_ERROR", "Hãy tìm bằng kỹ năng hoặc chức danh.", 422)
        try:
            vector = validate_vectors(
                get_embedder(settings).embed([safe_query]), 1, settings.embedding_dim
            )[0]
        except Exception:
            raise EmbeddingError() from None
        query = query.where(Candidate.embedding.is_not(None))
        order = [Candidate.embedding.cosine_distance(vector), Candidate.id]
    elif q:
        terms = func.plainto_tsquery("simple", func.unaccent(q))
        query = query.where(Candidate.search_tsv.op("@@")(terms))
        order = [func.ts_rank_cd(Candidate.search_tsv, terms).desc(), *order]
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        session.scalars(query.order_by(*order).offset((page - 1) * page_size).limit(page_size))
    )
    return CandidateList(items=summaries(session, rows), total=total)


def suggestions(session: Session, actor: User, job_id: UUID, limit: int) -> CandidateList:
    job = accessible_job(session, actor, job_id)
    authorize(actor, "cv_bank.search")
    if job.embedding is None:
        return CandidateList(items=[], total=0)
    existing = (
        select(Application.id)
        .where(
            Application.candidate_id == Candidate.id,
            Application.job_id == job.id,
            Application.deleted_at.is_(None),
        )
        .exists()
    )
    rows = list(
        session.scalars(
            summaries_query()
            .where(Candidate.embedding.is_not(None), ~existing)
            .order_by(Candidate.embedding.cosine_distance(job.embedding), Candidate.id)
            .limit(limit)
        )
    )
    return CandidateList(items=summaries(session, rows), total=len(rows))


def merge(session: Session, actor: User, source_id: UUID, target_id: UUID) -> CandidateBrief:
    authorize(actor, "cv_bank.merge")
    if source_id == target_id:
        raise AppError("INVALID_MERGE", "Hãy chọn hai ứng viên khác nhau.", 422)
    # Share identity matching's lock, then acquire candidate/application rows in
    # stable order. Creation also locks the candidate before its application.
    session.execute(select(func.pg_advisory_xact_lock(0x4356, 10)))
    session.scalars(
        select(Candidate)
        .where(Candidate.id.in_([source_id, target_id]))
        .order_by(Candidate.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    source = eligible_candidate(session, source_id)
    target = eligible_candidate(session, target_id)
    # Request creation holds the same Candidate lock. Check both identities
    # after waiting, so an accepted deletion request never loses its subject.
    if session.scalar(
        select(DataRequest.id)
        .where(
            DataRequest.candidate_id.in_([source_id, target_id]),
            DataRequest.kind == "delete",
            DataRequest.status == "open",
        )
        .limit(1)
    ):
        raise AppError("DATA_REQUEST_OPEN", "Không thể gộp hồ sơ đang có yêu cầu xoá dữ liệu.", 409)
    with session.begin_nested():
        applications = session.scalars(
            select(Application)
            .where(Application.candidate_id.in_([source_id, target_id]))
            .order_by(Application.id)
            .with_for_update()
        ).all()
        target_jobs = {
            a.job_id for a in applications if a.candidate_id == target_id and a.deleted_at is None
        }
        now = datetime.now(UTC)
        for application in applications:
            if application.candidate_id == source_id:
                if application.deleted_at is None and application.job_id in target_jobs:
                    application.deleted_at = now
        # Release partial-unique slots before changing candidate_id. Keep archived
        # applications and their history/feedback intact under their original IDs.
        session.flush()
        for application in applications:
            if application.candidate_id == source_id:
                application.candidate_id = target_id
        session.execute(
            update(CvFile).where(CvFile.candidate_id == source_id).values(candidate_id=target_id)
        )
        session.execute(
            update(Activity)
            .where(Activity.candidate_id == source_id)
            .values(candidate_id=target_id)
        )
        source.merged_into_id = target_id
        source.deleted_at = now
        log_activity(
            session,
            type=ActivityType.note,
            actor_id=actor.id,
            candidate_id=target_id,
            payload={
                "action": "candidate_merged",
                "source_id": str(source_id),
                "target_id": str(target_id),
            },
        )
        snapshot = CandidateBrief.model_validate(target)
    session.commit()
    return snapshot
