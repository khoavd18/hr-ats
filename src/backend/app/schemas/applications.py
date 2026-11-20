from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    candidate_id: UUID
    job_id: UUID
