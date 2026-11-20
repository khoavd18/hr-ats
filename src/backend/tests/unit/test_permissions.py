from uuid import uuid4

import pytest

from app.core.errors import AppError
from app.core.permissions import ResourceScope, authorize
from app.models.users import User, UserRole


@pytest.mark.parametrize("role", list(UserRole))
@pytest.mark.parametrize(
    ("action", "roles"),
    [
        ("users.manage", {"admin"}),
        ("data_requests.manage", {"admin"}),
        ("audit_log.view", {"admin"}),
        ("email_templates.manage", {"admin", "lead"}),
        ("hiring_units.manage", {"admin", "lead"}),
        ("cv_bank.search", {"admin", "lead", "recruiter"}),
        ("jobs.view", {"admin", "lead"}),
        ("job_candidates.view", {"admin", "lead"}),
        ("applications.move", {"admin", "lead"}),
        ("emails.send", {"admin", "lead"}),
        ("reports.view", {"admin", "lead"}),
    ],
)
def test_permission_matrix(role, action, roles):
    user = User(id=uuid4(), role=role, is_active=True)
    if role in roles:
        authorize(user, action)
    else:
        with pytest.raises(AppError) as error:
            authorize(user, action)
        assert error.value.status == 403


@pytest.mark.parametrize(
    "action", ["jobs.view", "job_candidates.view", "applications.move", "emails.send"]
)
def test_recruiter_requires_owner_or_membership(action):
    user = User(id=uuid4(), role=UserRole.recruiter, is_active=True)
    authorize(user, action, ResourceScope(owner_id=user.id))
    authorize(user, action, ResourceScope(member_ids=frozenset({user.id})))
    with pytest.raises(AppError):
        authorize(user, action, ResourceScope(owner_id=uuid4()))


def test_recruiter_can_only_view_own_report():
    user = User(id=uuid4(), role=UserRole.recruiter, is_active=True)
    authorize(user, "reports.view", ResourceScope(owner_id=user.id))
    with pytest.raises(AppError):
        authorize(user, "reports.view", ResourceScope(owner_id=uuid4()))


@pytest.mark.parametrize("role", list(UserRole))
def test_inactive_users_and_unknown_actions_are_denied(role):
    user = User(id=uuid4(), role=role, is_active=False)
    with pytest.raises(AppError):
        authorize(user, "cv_bank.search")
    user.is_active = True
    with pytest.raises(AppError):
        authorize(user, "unknown.action")
