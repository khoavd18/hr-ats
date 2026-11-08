from copy import deepcopy
from datetime import datetime
from math import isfinite
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import redact, sensitive_key
from app.models.activity import Activity
from app.models.enums import ActivityType


def _safe_payload(value: Any, depth: int = 0) -> bool:
    # Free text must never be used to copy CV contents into the activity stream.
    if depth > 8:
        return False
    if isinstance(value, dict):
        return all(
            isinstance(key, str)
            and not sensitive_key(key)
            and key not in {"cv", "parsed_json", "education", "experiences", "skills"}
            and _safe_payload(item, depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return all(_safe_payload(item, depth + 1) for item in value)
    if isinstance(value, float):
        return isfinite(value)
    return value is None or isinstance(value, (str, bool, int))


def log_activity(
    session: Session,
    *,
    type: ActivityType,
    actor_id: UUID | None = None,
    job_id: UUID | None = None,
    application_id: UUID | None = None,
    candidate_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> Activity:
    """Append within the caller's transaction. Callers pass metadata, never CV content.

    Rejection errors intentionally contain neither the offending key nor its value.
    """
    metadata = deepcopy(payload) if payload is not None else {}
    if (
        not isinstance(metadata, dict)
        or not _safe_payload(metadata)
        or redact(metadata) != metadata
    ):
        raise ValueError("Activity payload must contain non-sensitive JSON metadata only")
    activity = Activity(
        type=type,
        actor_id=actor_id,
        job_id=job_id,
        application_id=application_id,
        candidate_id=candidate_id,
        payload=metadata,
    )
    if occurred_at is not None:
        activity.occurred_at = occurred_at
    session.add(activity)
    session.flush()
    return activity
