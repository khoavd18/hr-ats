from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import DB, CurrentUser
from app.schemas.users import UserCreate, UserList, UserPatch, UserResponse
from app.services import users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserList)
def list_users(
    session: DB,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserList:
    return users.list_users(session, actor, page, page_size)


@router.post("", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, session: DB, actor: CurrentUser):
    return users.create_user(session, actor, data)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: UUID, data: UserPatch, session: DB, actor: CurrentUser):
    return users.update_user(session, actor, user_id, data)
