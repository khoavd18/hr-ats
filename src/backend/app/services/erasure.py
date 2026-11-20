"""Erasure of CVs that were accepted before a deletion but parsed after it.

A queued CV has no candidate until it is parsed, so the purge cannot find it by
candidate id. Freeze records keyed hashes of the erased person's contacts; the
worker compares a parsed CV's contacts with them and, when the CV was received
before the deletion, erases the file instead of recreating the person. A CV
received after the deletion is a new submission and is processed normally.

Only HMAC digests are stored, never a readable contact, and they are removed as
soon as no CV from before the deletion is still waiting to be processed.
"""

import hashlib
import hmac
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, delete, exists, null, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Activity, Candidate, CvFile, ErasedContact, InboundEmail
from app.models.enums import ProcessingStatus
from app.storage import Storage, StorageError


def contact_hash(value: str) -> str:
    key = get_settings().secret_key.get_secret_value().encode()
    return hmac.new(key, ("contact:" + value.strip().lower()).encode(), hashlib.sha256).hexdigest()


def _contacts(emails: Iterable[str | None], phones: Iterable[str | None]) -> set[str]:
    return {contact_hash(value) for value in [*emails, *phones] if value}


def record_erased_contacts(
    session: Session, people: Iterable[Candidate], frozen_at: datetime
) -> None:
    """Call inside the freeze transaction, while contacts are still readable."""
    digests = set()
    for person in people:
        digests |= _contacts([person.email], [person.phone])
    for digest in sorted(digests):
        session.add(ErasedContact(contact_hash=digest, frozen_at=frozen_at))
    session.flush()


def erased_before(
    session: Session, *, emails: list[str], phones: list[str], received_at: datetime
) -> bool:
    """True when this CV belongs to a person erased after the CV was received.

    The caller must hold the identity advisory lock (0x4356, 10), which freeze
    also takes, so a freeze cannot commit between this check and saving.
    """
    digests = _contacts(emails, phones)
    if not digests:
        return False
    return bool(
        session.scalar(
            select(
                exists().where(
                    ErasedContact.contact_hash.in_(digests),
                    ErasedContact.frozen_at >= received_at,
                )
            )
        )
    )


def _inbound_references(session: Session, file_id: UUID) -> list[UUID]:
    found: list[UUID] = []
    for payload in session.scalars(
        select(Activity.payload).where(Activity.payload["cv_file_id"].astext == str(file_id))
    ):
        for reference in (payload or {}).get("inbound_messages", []):
            try:
                found.append(UUID(reference["inbound_email_id"]))
            except (ValueError, TypeError, KeyError):
                continue
    return found


def erase_unlinked_file(session: Session, storage: Storage, file: CvFile, now: datetime) -> None:
    """Erase a CV that belongs to an erased person. Never links it to anyone."""
    inbound_ids = _inbound_references(session, file.id)
    key = file.storage_key
    if key:
        try:
            storage.delete(key)
            file.storage_key = None
        except StorageError:
            # Keep the key so the daily retention job can retry the deletion;
            # the row is already unusable (deleted, no hash, no content).
            pass
    file.original_filename = None
    file.sha256 = None
    file.extracted_text = None
    file.parsed_json = null()  # SQL NULL, as the purge writes
    file.parse_model = None
    file.parse_prompt_version = None
    file.error = None
    file.status = ProcessingStatus.failed
    file.deleted_at = now
    session.execute(
        update(Activity)
        .where(Activity.payload["cv_file_id"].astext == str(file.id))
        .values(payload={})
    )
    for inbound in session.scalars(
        select(InboundEmail).where(InboundEmail.id.in_(inbound_ids)).with_for_update()
    ):
        if inbound.message_id and not inbound.message_id.startswith("purged:"):
            inbound.message_id = "purged:" + hashlib.sha256(inbound.message_id.encode()).hexdigest()
        inbound.from_email = None
        inbound.subject = None
        inbound.error = None
        inbound.deleted_at = now
    session.flush()


def sweep_erased_files(session: Session, storage: Storage) -> None:
    """Retry blob deletion for erased unlinked files (storage was unavailable)."""
    for file in session.scalars(
        select(CvFile)
        .where(
            CvFile.candidate_id.is_(None),
            CvFile.deleted_at.is_not(None),
            CvFile.sha256.is_(None),
            CvFile.storage_key.is_not(None),
        )
        .with_for_update(skip_locked=True)
    ):
        try:
            storage.delete(file.storage_key)  # type: ignore[arg-type]
        except StorageError:
            continue
        file.storage_key = None
    session.commit()


def prune_erased_contacts(session: Session) -> None:
    """Drop markers once no CV received before that deletion is still queued."""
    waiting = exists().where(
        and_(
            CvFile.status.in_([ProcessingStatus.pending, ProcessingStatus.running]),
            CvFile.deleted_at.is_(None),
            CvFile.candidate_id.is_(None),
            CvFile.created_at <= ErasedContact.frozen_at,
        )
    )
    session.execute(delete(ErasedContact).where(~waiting))
    session.commit()
