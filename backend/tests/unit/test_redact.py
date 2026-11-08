"""All contacts below are fabricated, using reserved domains and dummy numbers."""

import pytest

from app.ai.redact import redact_contacts


@pytest.mark.parametrize(
    "original,canonical",
    [
        ("0900000001", "+84900000001"),
        ("0900 000 001", "+84900000001"),
        ("090 000 0001", "+84900000001"),
        ("0900.000.001", "+84900000001"),
        ("0900-000-001", "+84900000001"),
        ("0900\u00a0000\u00a0001", "+84900000001"),
        ("+84900000001", "+84900000001"),
        ("+84 900 000 001", "+84900000001"),
        ("+84 (0) 900-000-001", "+84900000001"),
        ("+84 0900 000 001", "+84900000001"),
        ("0084 900.000.001", "+84900000001"),
        ("0084 (0) 900 000 001", "+84900000001"),
        ("0300 000 001", "+84300000001"),
        ("0500 000 001", "+84500000001"),
        ("0700 000 001", "+84700000001"),
        ("0800 000 001", "+84800000001"),
        ("024 0000 0001", "+842400000001"),
        ("(028) 0000-0001", "+842800000001"),
        ("+84 28 0000 0001", "+842800000001"),
        ("+1 (202) 555-0100", "+12025550100"),
        ("001 202 555 0100", "+12025550100"),
    ],
)
def test_phone_variants_are_fully_masked_and_canonical(original: str, canonical: str) -> None:
    redacted, emails, phones = redact_contacts(f"Liên hệ: {original}; Kỹ năng: python")
    assert redacted == "Liên hệ: [PHONE]; Kỹ năng: python"
    assert original not in redacted
    assert emails == [] and phones == [canonical]


@pytest.mark.parametrize(
    "original",
    [
        "fixture@example.com",
        "FIRST.LAST@example.com",
        "fixture+cv@example.com",
        "fixture_cv@example.com",
        "fixture-cv@sub.example.com",
        "fixture.o'cv@example.com",
        "900000001@example.com",
        "fixture@sub-domain.example.com",
    ],
)
def test_email_variants_keep_original_local_value_and_mask_text(original: str) -> None:
    redacted, emails, phones = redact_contacts(f"Email: <{original}>.")
    assert redacted == "Email: <[EMAIL]>."
    assert original not in redacted
    assert emails == [original] and phones == []


def test_contacts_are_removed_everywhere_but_returned_once_in_first_seen_order() -> None:
    text = (
        "fixture@example.com / 0900 000 001\n"
        "second@example.com; +84 900 000 001; fixture@example.com\n"
        "0900000002 0900000003"
    )
    redacted, emails, phones = redact_contacts(text)
    assert redacted == "[EMAIL] / [PHONE]\n[EMAIL]; [PHONE]; [EMAIL]\n[PHONE] [PHONE]"
    assert emails == ["fixture@example.com", "second@example.com"]
    assert phones == ["+84900000001", "+84900000002", "+84900000003"]
    assert redact_contacts(redacted) == (redacted, [], [])


def test_dates_experience_versions_short_numbers_and_boundaries_are_unchanged() -> None:
    text = (
        "Ngày sinh: 2000-01-01\nKinh nghiệm: 2020-01 - 2026-01; 6 năm\n"
        "Python 3.12; GPA 3.5; 12345; ABC0900000001; 090000000112345\n"
        "Mã: 840000001; [EMAIL]; [PHONE]"
    )
    assert redact_contacts(text) == (text, [], [])
    assert redact_contacts("") == ("", [], [])


def test_phone_cannot_consume_digits_on_next_line() -> None:
    text = "0900 000 001\n2026-01"
    assert redact_contacts(text) == ("[PHONE]\n2026-01", [], ["+84900000001"])
