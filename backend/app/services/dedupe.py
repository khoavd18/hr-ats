"""Candidate identity matching. No content, contacts or SQL errors are logged."""

import unicodedata
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai.schemas import ParsedCV
from app.core.errors import AppError
from app.models.candidates import Candidate
from app.models.enums import CandidateSource


class IdentityConflict(AppError):
    def __init__(self) -> None:
        super().__init__(
            "CV_IDENTITY_CONFLICT",
            "Email và số điện thoại khớp nhiều ứng viên. Cần kiểm tra thủ công.",
            409,
        )


def match_candidate(session: Session, *, emails: list[str], phones: list[str]) -> Candidate | None:
    # A distinct two-int advisory lock namespace avoids the upload's hash locks.
    # Held until commit, including when there is no existing row to lock yet.
    session.execute(select(func.pg_advisory_xact_lock(0x4356, 10)))
    if not emails and not phones:
        return None
    matches = session.scalars(
        select(Candidate)
        .where(
            Candidate.deleted_at.is_(None),
            Candidate.merged_into_id.is_(None),
            or_(
                Candidate.email.in_([email.lower() for email in emails]),
                Candidate.phone.in_(phones),
            ),
        )
        .order_by(Candidate.id)
        .with_for_update()
    ).all()
    if len(matches) > 1:
        raise IdentityConflict()
    return matches[0] if matches else None


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())


def save_candidate(
    session: Session,
    *,
    parsed: ParsedCV,
    emails: list[str],
    phones: list[str],
    retention_until: date,
    source: CandidateSource = CandidateSource.upload,
) -> Candidate:
    candidate = match_candidate(session, emails=emails, phones=phones)
    if candidate is None:
        candidate = Candidate(full_name=parsed.full_name or "Chưa xác định", source=source)
        session.add(candidate)
    # Null/empty parse fields mean unknown, not a request to erase known data.
    for name in ("full_name", "current_title", "location"):
        value = getattr(parsed, name)
        if value is not None:
            setattr(candidate, name, value)
    if parsed.years_experience is not None:
        candidate.years_experience = Decimal(str(parsed.years_experience))
    values = parsed.model_dump(mode="json")
    for name in ("skills", "languages", "education", "experiences"):
        if values[name]:
            setattr(candidate, name, values[name])
    if emails:
        candidate.email = emails[0].lower()
    if phones:
        candidate.phone = phones[0]
    candidate.retention_until = retention_until
    session.flush()
    return candidate


def possible_duplicate(
    session: Session,
    *,
    full_name: str | None,
    embedding: list[float] | None,
    exclude_id: UUID,
) -> UUID | None:
    """Call only for a CV without contacts, after the T11 embedding hook.

    An absent/zero embedding never supplies evidence of duplication. Return a
    suggestion only; no merge, deletion or recruiting decision occurs here.
    """
    if not full_name or embedding is None or not any(embedding):
        return None
    distance = Candidate.embedding.cosine_distance(embedding)
    rows = session.execute(
        select(Candidate.id, Candidate.full_name)
        .where(
            Candidate.id != exclude_id,
            Candidate.deleted_at.is_(None),
            Candidate.merged_into_id.is_(None),
            Candidate.embedding.is_not(None),
            distance < 0.05,
        )
        .order_by(distance, Candidate.id)
    )
    name = normalize_name(full_name)
    return next((row.id for row in rows if normalize_name(row.full_name) == name), None)
