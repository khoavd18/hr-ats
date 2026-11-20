"""SMTP boundary: no protocol debugging, addresses, content or exceptions in logs."""

import smtplib
import ssl
from email.message import EmailMessage as MIMEMessage
from html.parser import HTMLParser

from app.core.config import Settings


def plain_text(html: str) -> str:
    """Recover readable text from escaped Markdown and internal report tables."""

    class Text(HTMLParser):
        def handle_data(self, data: str) -> None:
            parts.append(data)

        def handle_starttag(self, tag: str, attrs) -> None:
            if tag in {"p", "br", "li", "tr", "h1", "h2", "h3"}:
                parts.append("\n")
            elif tag in {"td", "th"}:
                parts.append("\t")

    parts: list[str] = []
    parser = Text()
    parser.feed(html)
    parser.close()
    return "".join(parts).strip()


def deliver(settings: Settings, message: MIMEMessage, recipient: str) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_tls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        refused = smtp.send_message(message, to_addrs=[recipient])
        if refused:
            raise smtplib.SMTPException("SMTP delivery failed")
