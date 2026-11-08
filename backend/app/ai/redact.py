"""Remove contact details before parsing; returned contacts stay local."""

import re

_EMAIL = re.compile(
    r"(?<![\w.+-])[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,63}(?![\w-])"
)
_SEP = r"[ \t\u00a0().-]*"
# Vietnamese mobiles have nine national digits, landlines ten (initial 2).
# Keep the national alternatives bounded so adjacent Vietnamese numbers stay separate.
_PHONE = re.compile(
    r"(?<![\w+])(?:"
    rf"(?:(?:\+84|0084){_SEP}(?:(?:\(0\)|0){_SEP})?|\(?0{_SEP})"
    rf"(?:2(?:{_SEP}[0-9]){{9}}|[1-9](?:{_SEP}[0-9]){{8}})"
    rf"|(?:\+(?!84)|00(?!84))[1-9](?:{_SEP}[0-9]){{6,14}}"
    r")(?!\w)"
)


def _canonical_phone(raw: str) -> str:
    digits = re.sub(r"[^0-9]", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    elif not raw.startswith("+"):
        return "+84" + digits[1:]
    if digits.startswith("840"):
        digits = "84" + digits[3:]
    return "+" + digits


def redact_contacts(text: str) -> tuple[str, list[str], list[str]]:
    """Return masked text, original emails and canonical phones, in first-seen order.

    Only emails/phones are masked here. T11 anonymizes names and other personal
    details before embedding/scoring. Never log any of these inputs or outputs.
    """
    emails: list[str] = []
    phones: list[str] = []

    def email(match: re.Match[str]) -> str:
        original = match.group()
        if original not in emails:
            emails.append(original)
        return "[EMAIL]"

    def phone(match: re.Match[str]) -> str:
        canonical = _canonical_phone(match.group())
        if canonical not in phones:
            phones.append(canonical)
        return "[PHONE]"

    return _PHONE.sub(phone, _EMAIL.sub(email, text)), emails, phones
