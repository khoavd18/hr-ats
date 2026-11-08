"""Local, deterministic CV redaction. Never logs text or inferred identities."""

import re
import unicodedata

from app.ai.redact import redact_contacts


def _fold(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
        if not unicodedata.combining(char)
    )


def _mask_name(text: str, name: str) -> str:
    # Map folded offsets back to NFC text so accents/case of professional text
    # remain intact, even when casefold expands a character (e.g. sharp s).
    folded, offsets = "", []
    for index, char in enumerate(text):
        piece = _fold(char)
        folded += piece
        offsets.extend([index] * len(piece))
    words = _fold(name).split()
    if not words:
        return text
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in words) + r"(?!\w)"
    for match in reversed(list(re.finditer(pattern, folded))):
        text = text[: offsets[match.start()]] + "[TÊN]" + text[offsets[match.end() - 1] + 1 :]
    return text


_NAME_LABEL = re.compile(r"^\s*(?:ho(?: va)? ten|full name|name)\s*[:：]\s*", re.I)
_PRIVATE_LABEL = re.compile(
    r"(?:^|[|;•])\s*(?:ngay sinh|nam sinh|sinh ngay|sinh nam|tuoi|gioi tinh|"
    r"tinh trang hon nhan|hon nhan|dia chi(?: nha| thuong tru| hien tai)?|"
    r"noi o|noi cu tru|ho khau|date of birth|birth date|dob|year of birth|age|"
    r"gender|sex|marital status|home address|address|residence)\b"
    r"(?:\s*[:：=\-]|\s+(?=\d)|\s*$)",
    re.I,
)
_GENDER_LINE = re.compile(r"^\s*(?:nam|nu|male|female|man|woman)\s*[.!]?\s*$")
_GENDER_PHRASE = re.compile(
    r"\b(?:toi la|ung vien|i am|candidate)\s+(?:nam|nu|male|female)\b"
    r"|\b\d{1,3}\s*(?:tuoi|years? old)\b"
)
_SOCIAL_URL = re.compile(
    r"(?i)(?:https?://)?(?:www\.)?"
    r"(?:facebook\.com|fb\.com|fb\.me|linkedin\.com|instagram\.com|"
    r"tiktok\.com|twitter\.com|x\.com|zalo\.me|github\.com|gitlab\.com)"
    r"(?:/[^\s<>]*)?(?![\w.])"
)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<img\b[^>]*>", re.I)


def anonymize(text: str, full_name: str | None) -> str:
    """Mask known/labeled names and remove personal metadata in VI/EN.

    Names supplied by parsing are preferred. Labeled names are also collected
    locally, including when parsing returned null. This is a heuristic, not NER.
    Images never enter extraction; strip image markup defensively as well.
    """
    text = unicodedata.normalize("NFC", text)
    text, _, _ = redact_contacts(text)
    names = {full_name} if full_name else set()
    for line in text.splitlines():
        match = _NAME_LABEL.match(_fold(line))
        if match:
            # Prefix is ASCII after folding; find its delimiter in original text.
            names.add(re.split(r"[:：]", line, maxsplit=1)[1].split("|")[0].strip())
    for name in sorted(names, key=lambda value: (-len(value), value)):
        text = _mask_name(text, name)
    if "[TÊN]" not in text:
        # A null parse must not expose the common unlabeled name at the top.
        # Conservatively mask an alphabetic header, never infer/store an identity.
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if (
            re.fullmatch(r"[^\W\d_]+(?:[ \t]+[^\W\d_]+){1,5}", first)
            and not _PRIVATE_LABEL.search(_fold(first))
            and not _GENDER_PHRASE.search(_fold(first))
        ):
            text = _mask_name(text, first)
    text = _IMAGE.sub("", text)
    text = _SOCIAL_URL.sub("[LINK]", text)
    lines = []
    skip_value = False
    for line in text.splitlines():
        if not line.strip():
            continue
        if skip_value:
            skip_value = False
            continue
        folded = _fold(line)
        # Removing the whole metadata line is deliberate: unknown formatting
        # should not leak the rest of a home address or a second personal field.
        private = _PRIVATE_LABEL.search(folded)
        if private:
            skip_value = not folded[private.end() :].strip()
            continue
        if _GENDER_LINE.fullmatch(folded):
            continue
        if _GENDER_PHRASE.search(folded):
            continue
        lines.append(line.strip())
    return "\n".join(line for line in lines if line).strip()
