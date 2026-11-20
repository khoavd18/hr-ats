import smtplib
import socket
from email.message import EmailMessage

import pytest
from celery import current_app

from app.core.config import get_settings


def test_test_mode_uses_fake_ai_and_eager_in_memory_celery() -> None:
    settings = get_settings()
    assert settings.app_env == "test"
    assert settings.llm_provider == settings.embedding_provider == "fake"
    assert settings.database_url.endswith("/hr_ats_test")
    assert current_app.conf.task_always_eager is True
    assert current_app.conf.broker_url == "memory://"


def test_external_dns_and_direct_connections_are_blocked() -> None:
    with pytest.raises(AssertionError, match="External network"):
        socket.getaddrinfo("example.invalid", 443)
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="External network"):
            connection.connect(("192.0.2.1", 443))
        with pytest.raises(AssertionError, match="External network"):
            connection.connect_ex(("192.0.2.1", 443))


def test_email_is_kept_in_memory(email_outbox: list) -> None:
    message = EmailMessage()
    message["From"] = "sender@example.invalid"
    message["To"] = "recipient@example.invalid"
    message.set_content("Thông báo giả phục vụ kiểm thử.")
    with smtplib.SMTP("smtp.example.invalid") as smtp:
        smtp.send_message(message)
    assert email_outbox == [message]
