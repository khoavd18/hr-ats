from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.models.users import UserRole


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class EmailInput(InputModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.partition("@")
        if (
            not separator
            or not local
            or "." not in domain
            or "@" in domain
            or any(c.isspace() or ord(c) < 32 for c in value)
        ):
            raise ValueError("Invalid email")
        return value


Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]


class LoginInput(EmailInput):
    password: SecretStr = Field(min_length=1, max_length=128)


class ChangePasswordInput(InputModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: Password


class UserCreate(EmailInput):
    full_name: str = Field(min_length=1, max_length=200)
    role: UserRole
    password: Password

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name required")
        return value


class UserPatch(InputModel):
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("role", "is_active")
    @classmethod
    def disallow_explicit_null(cls, value):
        if value is None:
            raise ValueError("Null not permitted")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserList(BaseModel):
    items: list[UserResponse]
    total: int
