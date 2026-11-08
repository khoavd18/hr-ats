from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import authorize
from app.core.security import hash_password
from app.models.users import User, UserRole
from app.schemas.users import UserCreate, UserList, UserPatch, UserResponse


def list_users(session: Session, actor: User, page: int, page_size: int) -> UserList:
    authorize(actor, "users.manage")
    users = session.scalars(
        select(User)
        .order_by(User.created_at, User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = session.scalar(select(func.count()).select_from(User)) or 0
    return UserList(items=[UserResponse.model_validate(user) for user in users], total=total)


def create_user(session: Session, actor: User | None, data: UserCreate) -> User:
    # actor=None is reserved for the local administrator bootstrap CLI, never an API input.
    if actor is not None:
        authorize(actor, "users.manage")
    user = User(
        email=data.email,
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(data.password.get_secret_value()),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AppError("EMAIL_EXISTS", "Email này đã có tài khoản.", 409) from None
    session.refresh(user)
    return user


def update_user(session: Session, actor: User, user_id: UUID, data: UserPatch) -> User:
    authorize(actor, "users.manage")
    if actor.id == user_id and (data.is_active is False or data.role not in {None, UserRole.admin}):
        raise AppError("SELF_LOCKOUT", "Không thể tự khoá hoặc bỏ quyền quản trị của bạn.", 409)
    user = session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise AppError("NOT_FOUND", "Không tìm thấy người dùng.", 404)
    changes = data.model_dump(exclude_unset=True)
    if any(getattr(user, key) != value for key, value in changes.items()):
        for key, value in changes.items():
            setattr(user, key, value)
        user.auth_version += 1
    session.commit()
    return user
