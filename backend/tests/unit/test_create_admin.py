import sys

from sqlalchemy import select

from app.models.users import User
from app.scripts import create_admin


def test_cli_prompts_for_password_and_does_not_print_credentials(db_session, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["create_admin", "--email", "cli-admin@example.invalid"])
    monkeypatch.setattr(create_admin, "getpass", lambda _: "synthetic-cli-password")

    class TestSession:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return db_session

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(create_admin, "Session", TestSession)
    assert create_admin.main() == 0
    user = db_session.scalar(select(User).where(User.email == "cli-admin@example.invalid"))
    assert user.role == "admin" and user.password_hash.startswith("$argon2id$")
    assert create_admin.main() == 1  # No duplicate or overwrite.
    output = capsys.readouterr().out
    assert "cli-admin@" not in output and "synthetic-cli-password" not in output


def test_cli_rejects_mismatch_without_writing(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["create_admin", "--email", "cli-admin@example.invalid"])
    passwords = iter(["synthetic-cli-password", "another-synthetic-password"])
    monkeypatch.setattr(create_admin, "getpass", lambda _: next(passwords))
    assert create_admin.main() == 1
    assert "không khớp" in capsys.readouterr().out
