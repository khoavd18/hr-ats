"""Load the deliberately small frontmatter format without a YAML dependency."""

import re
from dataclasses import dataclass, field

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from app.core.config import REPO_ROOT
from app.core.errors import AppError

PROMPTS_DIR = REPO_ROOT / "prompts"
_ENV = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)


class PromptError(AppError):
    def __init__(self) -> None:
        super().__init__("INVALID_PROMPT", "Không tải được mẫu xử lý AI.", 500)


@dataclass(frozen=True)
class RenderedPrompt:
    task: str
    version: int
    system: str = field(repr=False)
    user: str = field(repr=False)

    @property
    def prompt_version(self) -> str:
        return f"v{self.version}"


@dataclass(frozen=True)
class PromptTemplate:
    task: str
    version: int
    description: str
    system: str = field(repr=False)
    user: str = field(repr=False)

    def render(self, **variables: object) -> RenderedPrompt:
        try:
            return RenderedPrompt(
                task=self.task,
                version=self.version,
                system=_ENV.from_string(self.system).render(**variables),
                user=_ENV.from_string(self.user).render(**variables),
            )
        except (TemplateError, TypeError, ValueError):
            raise PromptError() from None


def load_prompt(task: str, version: int = 1) -> PromptTemplate:
    if re.fullmatch(r"[a-z][a-z0-9_]*", task) is None or type(version) is not int or version < 1:
        raise PromptError()
    root = PROMPTS_DIR.resolve()
    path = (root / task / f"v{version}.md").resolve()
    if not path.is_relative_to(root):
        raise PromptError()
    try:
        source = path.read_text(encoding="utf-8")
        match = re.fullmatch(
            r"---\n(.*?)\n---\n\s*## system\n(.*?)\n## user\n(.*)", source, re.DOTALL
        )
        if match is None:
            raise PromptError()
        metadata = {}
        for line in match[1].splitlines():
            key, value = line.split(":", 1)
            if key in metadata:
                raise PromptError()
            metadata[key] = value.strip()
        if (
            set(metadata) != {"version", "task", "description"}
            or metadata["version"] != str(version)
            or metadata["task"] != task
            or not metadata["description"]
            or not match[2].strip()
            or not match[3].strip()
        ):
            raise PromptError()
        return PromptTemplate(
            task, version, metadata["description"], match[2].strip(), match[3].strip()
        )
    except (OSError, UnicodeError, ValueError):
        raise PromptError() from None
