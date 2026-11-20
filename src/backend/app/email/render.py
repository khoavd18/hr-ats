"""Bounded, flat-variable Jinja templates and a deliberately small safe Markdown dialect."""

import re
from dataclasses import dataclass
from html import escape

from jinja2 import StrictUndefined, TemplateError, nodes
from jinja2.sandbox import SandboxedEnvironment

from app.core.errors import AppError

VARIABLES = (
    "candidate_name",
    "job_title",
    "hiring_unit_name",
    "interview_time",
    "interview_location",
    "offer_salary",
    "offer_start_date",
    "recruiter_name",
    "recruiter_email",
    "company_name",
)
MAX_BODY = 20000
MAX_OUTPUT = 100000


def environment() -> SandboxedEnvironment:
    env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
    env.globals.clear()
    env.filters.clear()
    env.tests.clear()
    return env


def invalid_template() -> AppError:
    return AppError(
        "EMAIL_TEMPLATE_INVALID",
        "Mẫu chưa hợp lệ. Chỉ dùng văn bản và các biến được chèn bằng nút.",
        422,
    )


def validate_template(source: str) -> set[str]:
    if len(source) > MAX_BODY:
        raise invalid_template()
    # Bound parsing too: reject nested/computed syntax before invoking the Jinja parser.
    literals = re.sub(r"{{\s*[a-z][a-z0-9_]*\s*}}", "", source)
    if any(marker in literals for marker in ("{{", "{%", "{#", "}}", "%}", "#}")):
        raise invalid_template()
    try:
        tree = environment().parse(source)
    except TemplateError:
        raise invalid_template() from None
    names: set[str] = set()
    for node in tree.find_all(nodes.Node):
        if not isinstance(node, (nodes.Output, nodes.TemplateData, nodes.Name)):
            raise invalid_template()
        if isinstance(node, nodes.Name):
            if node.name not in VARIABLES:
                # Name is a bounded identifier, never a raw exception or a context value.
                raise AppError(
                    "EMAIL_VARIABLE_UNKNOWN", "Biến không được hỗ trợ: " + node.name[:64] + ".", 422
                )
            names.add(node.name)
    return names


def markdown_html(source: str) -> str:
    """Escape all input first; emit only fixed paragraphs, breaks, lists and inline tags.

    No links, images, raw HTML, attributes or remote resources are supported.
    """

    def inline(value: str) -> str:
        value = escape(value, quote=True)
        value = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", value)
        value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", value)
        return value

    output: list[str] = []
    for block in re.split(r"\n\s*\n", source.replace("\r\n", "\n").strip()):
        lines = block.split("\n")
        if lines and all(line.startswith("- ") for line in lines):
            output.append(
                "<ul>" + "".join("<li>" + inline(line[2:]) + "</li>" for line in lines) + "</ul>"
            )
        else:
            output.append("<p>" + "<br>".join(inline(line) for line in lines) + "</p>")
    return "\n".join(output)


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    body: str
    body_html: str


def render_email(subject: str, body: str, context: dict[str, str]) -> RenderedEmail:
    names = validate_template(subject) | validate_template(body)
    for name in VARIABLES:
        if name in names and (not isinstance(context.get(name), str) or not context[name].strip()):
            raise AppError(
                "EMAIL_MISSING_" + name.upper(), "Thiếu thông tin cho biến: " + name + ".", 422
            )
    # Never expose ORM objects, callables or extra caller-supplied context to Jinja.
    safe_context = {name: context[name] for name in names}
    # Conservative bound before allocating the rendered output, including repeated variables.
    for source in (subject, body):
        if (
            len(source)
            + sum(source.count(name) * len(value) for name, value in safe_context.items())
            > MAX_OUTPUT
        ):
            raise invalid_template()
    try:
        env = environment()
        rendered_subject = env.from_string(subject).render(safe_context)
        rendered_body = env.from_string(body).render(safe_context)
    except TemplateError:
        raise invalid_template() from None
    if (
        not rendered_subject.strip()
        or len(rendered_subject) > 500
        or any(char in rendered_subject for char in "\r\n\x00")
        or len(rendered_body) > MAX_OUTPUT
    ):
        raise invalid_template()
    return RenderedEmail(rendered_subject, rendered_body, markdown_html(rendered_body))
