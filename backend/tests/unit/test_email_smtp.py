from email.message import EmailMessage

from app.core.config import Settings
from app.email.smtp import deliver, plain_text


def test_text_alternative_preserves_literal_markup_and_paragraphs():
    assert plain_text("<p>Chào &lt;script&gt;</p><p>Tiếp<br>Đây</p>") == "Chào <script>\nTiếp\nĐây"


def test_smtp_uses_timeout_verified_starttls_credentials_and_explicit_recipient(monkeypatch):
    calls = []

    class SMTP:
        def __init__(self, host, port, timeout):
            calls.append((host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, *, context):
            assert context.check_hostname and context.verify_mode == 2
            calls.append("tls")

        def login(self, user, password):
            calls.append((user, password))

        def send_message(self, message, *, to_addrs):
            calls.append(to_addrs)
            return {}

    monkeypatch.setattr("smtplib.SMTP", SMTP)
    settings = Settings(
        smtp_tls=True, smtp_user="synthetic-user", smtp_password="synthetic-password"
    )
    deliver(settings, EmailMessage(), "synthetic@example.invalid")
    assert calls == [
        (settings.smtp_host, settings.smtp_port, 15),
        "tls",
        ("synthetic-user", "synthetic-password"),
        ["synthetic@example.invalid"],
    ]
