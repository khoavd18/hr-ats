"""Administrative candidate data requests; no public candidate portal."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import RecordMixin


class DataRequest(RecordMixin, Base):
    __tablename__ = "data_requests"
    __table_args__ = (
        CheckConstraint("kind IN ('delete', 'export')", name="ck_data_requests_kind"),
        CheckConstraint("status IN ('open', 'done', 'rejected')", name="ck_data_requests_status"),
        CheckConstraint(
            "(status = 'open' AND handled_at IS NULL AND handled_by IS NULL) OR "
            "(status <> 'open' AND handled_at IS NOT NULL)",
            name="ck_data_requests_handled",
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("candidates.id"), index=True)
    kind: Mapped[str] = mapped_column(String(6))
    requested_by_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(8), server_default=text("'open'"))
    handled_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ErasedContact(RecordMixin, Base):
    """Short-lived erasure marker: keyed hash of an erased email/phone.

    Lets a CV accepted before the deletion (still queued, identity unknown) be
    recognised and erased instead of recreating the person. Holds no readable
    contact. Rows are removed once no CV from before `frozen_at` is still queued.
    """

    __tablename__ = "erased_contacts"

    contact_hash: Mapped[str] = mapped_column(String(64), index=True)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
