from html.parser import HTMLParser

import pytest
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from app.core.errors import AppError
from app.email.defaults import DEFAULT_TEMPLATES
from app.email.render import VARIABLES, environment, render_email

CONTEXT = {name: f"Giá trị giả {index}" for index, name in enumerate(VARIABLES)}


def test_all_ten_variables_and_plain_subject_markdown_body():
    env = environment()
    assert isinstance(env, SandboxedEnvironment) and env.undefined is StrictUndefined
    result = render_email(
        "{{ job_title }}", "\n\n".join("{{ " + name + " }}" for name in VARIABLES), CONTEXT
    )
    assert result.subject == CONTEXT["job_title"]
    assert all(value in result.body_html for value in CONTEXT.values())
    result = render_email("Thư giả", "**Đậm** và *nghiêng*\n\n- Một\n- Hai\n\nBa\nBốn", {})
    assert (
        result.body_html == "<p><strong>Đậm</strong> và <em>nghiêng</em></p>\n"
        "<ul><li>Một</li><li>Hai</li></ul>\n<p>Ba<br>Bốn</p>"
    )


@pytest.mark.parametrize("name", VARIABLES)
@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_or_blank_variables_are_named_in_vietnamese(name, value):
    context = {} if value is None else {name: value}
    with pytest.raises(AppError) as error:
        render_email("Thư giả", "{{ " + name + " }}", context)
    assert error.value.status == 422
    assert error.value.code == "EMAIL_MISSING_" + name.upper()
    assert error.value.message == f"Thiếu thông tin cho biến: {name}."


@pytest.mark.parametrize(
    "source",
    [
        "{{ candidate_name.__class__.__mro__ }}",
        "{{ ''.__class__.__mro__[1].__subclasses__() }}",
        "{{ cycler.__init__.__globals__.os.popen('echo unsafe').read() }}",
        "{{ candidate_name.upper() }}",
        "{{ candidate_name|safe }}",
        "{% include 'secret' %}",
        "{% for x in range(10000000) %}x{% endfor %}",
        "{{ 'x' * 1000000000 }}",
        "{% set x = 1 %}{{ x }}",
        "{{ candidate_name[0] }}",
        "{{",
        "{{ unknown }}",
    ],
)
def test_sandbox_rejects_attribute_calls_filters_code_and_unknown_variables(source):
    with pytest.raises(AppError) as error:
        render_email("Thư giả", source, CONTEXT)
    assert error.value.status == 422
    assert error.value.code in {"EMAIL_TEMPLATE_INVALID", "EMAIL_VARIABLE_UNKNOWN"}


def test_scripts_and_context_values_are_escaped_and_never_rerendered():
    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
            assert attrs == []

    context = {"candidate_name": '<script>synthetic()</script> {{ job_title }} & "x"'}
    body = (
        "<script>alert(1)</script>\n<img src=x onerror=bad()>\n"
        "{{ candidate_name }}\n[link](javascript:bad)"
    )
    result = render_email("Thư giả", body, context)
    assert "&lt;script&gt;" in result.body_html
    assert "{{ job_title }}" in result.body_html
    assert "&amp; &quot;x&quot;" in result.body_html
    tags = Tags()
    tags.feed(result.body_html)
    assert set(tags.tags) == {"p", "br"}


@pytest.mark.parametrize(
    "subject,body,context",
    [
        ("A\r\nB", "Nội dung", {}),
        ("{{ candidate_name }}", "Nội dung", {"candidate_name": "A\nB"}),
        ("x" * 501, "Nội dung", {}),
        ("Thư", "x" * 20001, {}),
        ("Thư", "{{ candidate_name }}" * 100, {"candidate_name": "x" * 2000}),
    ],
)
def test_size_limits_and_header_injection(subject, body, context):
    with pytest.raises(AppError):
        render_email(subject, body, context)


def test_five_defaults_render_and_cv_received_contains_privacy_and_deletion_notice():
    assert {item["key"] for item in DEFAULT_TEMPLATES} == {
        "cv_received",
        "interview_invite",
        "rejection",
        "offer",
        "submitted_to_unit",
    }
    for item in DEFAULT_TEMPLATES:
        assert render_email(item["subject"], item["body"], CONTEXT).body_html
        assert item["requires_confirmation"] == (item["key"] != "cv_received")
    notice = next(item["body"] for item in DEFAULT_TEMPLATES if item["key"] == "cv_received")
    assert "xử lý" in notice and "dữ liệu cá nhân" in notice and "xoá hồ sơ" in notice
