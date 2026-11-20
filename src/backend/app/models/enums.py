from enum import StrEnum


class HiringUnitKind(StrEnum):
    client = "client"
    department = "department"


class JobStatus(StrEnum):
    draft = "draft"
    open = "open"
    on_hold = "on_hold"
    closed = "closed"


class ApplicationStage(StrEnum):
    new = "new"
    screening = "screening"
    submitted = "submitted"
    interview = "interview"
    offer = "offer"
    hired = "hired"
    rejected = "rejected"
    withdrawn = "withdrawn"


class AiLevel(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"
    insufficient = "insufficient"


class ProcessingStatus(StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class CandidateSource(StrEnum):
    upload = "upload"
    email = "email"
    form = "form"
    import_ = "import"


class ExtractionMethod(StrEnum):
    pdf_text = "pdf_text"
    docx = "docx"
    ocr = "ocr"
    plain = "plain"


class CriterionResult(StrEnum):
    met = "met"
    partial = "partial"
    not_met = "not_met"
    unknown = "unknown"


class EmailStatus(StrEnum):
    draft = "draft"
    queued = "queued"
    sent = "sent"
    failed = "failed"
    cancelled = "cancelled"


class TaskStatus(StrEnum):
    todo = "todo"
    doing = "doing"
    done = "done"
    cancelled = "cancelled"


class ActivityType(StrEnum):
    note = "note"
    call = "call"
    email_sent = "email_sent"
    stage_changed = "stage_changed"
    cv_uploaded = "cv_uploaded"
    ai_scored = "ai_scored"
    ai_feedback = "ai_feedback"
    interview_scheduled = "interview_scheduled"
    offer_made = "offer_made"
    task_done = "task_done"
