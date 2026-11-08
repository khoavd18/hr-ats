from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.ai.schemas import ParsedCV
from app.core.config import get_settings
from app.models import Candidate
from app.services.dedupe import (
    IdentityConflict,
    match_candidate,
    normalize_name,
    possible_duplicate,
)


def candidate(session, **kwargs):
    row = Candidate(full_name="Ứng viên giả", retention_until=date(2030, 1, 1), **kwargs)
    session.add(row)
    session.flush()
    return row


@pytest.mark.parametrize(
    ("emails", "phones"),
    [
        (["IDENTITY@example.invalid"], []),
        ([], ["+84900000123"]),
        (["other@example.invalid", "identity@example.invalid"], ["+84900000999"]),
    ],
)
def test_exact_contact_match_uses_any_local_contact(db_session, emails, phones):
    row = candidate(db_session, email="identity@example.invalid", phone="+84900000123")
    assert match_candidate(db_session, emails=emails, phones=phones).id == row.id


def test_conflicting_identities_are_never_merged(db_session):
    first = candidate(db_session, email="one@example.invalid")
    second = candidate(db_session, phone="+84900000123")
    with pytest.raises(IdentityConflict):
        match_candidate(db_session, emails=[first.email], phones=[second.phone])
    assert first.merged_into_id is second.merged_into_id is None


def test_soft_deleted_and_merged_records_are_not_reused(db_session):
    target = candidate(db_session)
    deleted = candidate(db_session, email="deleted@example.invalid", deleted_at=datetime.now(UTC))
    merged = candidate(db_session, phone="+84900000123", merged_into_id=target.id)
    assert match_candidate(db_session, emails=[deleted.email], phones=[merged.phone]) is None
    assert match_candidate(db_session, emails=[], phones=[]) is None


def test_possible_duplicate_requires_name_and_cosine_and_never_merges(db_session):
    dim = get_settings().embedding_dim
    vector = [1.0] + [0.0] * (dim - 1)
    row = candidate(db_session, embedding=vector)
    row.full_name = "  TRẦN  ĐỨC MÔ PHỎNG  "
    db_session.flush()
    kwargs = dict(full_name="tran duc mo phong", embedding=vector, exclude_id=uuid4())
    assert possible_duplicate(db_session, **kwargs) == row.id
    assert possible_duplicate(db_session, **{**kwargs, "full_name": "Khác tên"}) is None
    assert possible_duplicate(db_session, **{**kwargs, "full_name": None}) is None
    assert possible_duplicate(db_session, **{**kwargs, "embedding": None}) is None
    assert possible_duplicate(db_session, **{**kwargs, "embedding": [0.0] * dim}) is None
    below_threshold = [0.94, (1 - 0.94**2) ** 0.5] + [0.0] * (dim - 2)
    assert possible_duplicate(db_session, **{**kwargs, "embedding": below_threshold}) is None
    assert possible_duplicate(db_session, **{**kwargs, "exclude_id": row.id}) is None
    row.deleted_at = datetime.now(UTC)
    db_session.flush()
    assert possible_duplicate(db_session, **kwargs) is None
    assert row.merged_into_id is None


def test_normalize_name_handles_accents_case_and_whitespace():
    assert normalize_name("  ĐẶNG  MÔ\tPHỎNG ") == "dang mo phong"


def test_refresh_preserves_known_fields_and_consent(db_session):
    from app.services.dedupe import save_candidate

    row = candidate(
        db_session,
        email="keep@example.invalid",
        skills=["python"],
        consent_at=datetime.now(UTC),
        consent_note="Bằng chứng giả",
    )
    old_consent = row.consent_at
    parsed = ParsedCV(
        full_name=None,
        current_title=None,
        location=None,
        years_experience=0,
        skills=[],
        languages=[],
        experiences=[],
        education=[],
    )
    saved = save_candidate(
        db_session, parsed=parsed, emails=[row.email], phones=[], retention_until=date(2031, 1, 1)
    )
    assert saved.id == row.id and saved.full_name == "Ứng viên giả"
    assert saved.skills == ["python"] and saved.years_experience == 0
    assert saved.consent_at == old_consent and saved.consent_note == "Bằng chứng giả"
    assert saved.retention_until == date(2031, 1, 1)
