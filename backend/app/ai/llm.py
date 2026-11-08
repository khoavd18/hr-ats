"""Synchronous, bounded JSON adapters. No provider SDK, executable tools or agent loop."""

import json
import logging
import math
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from app.ai.schemas import ParseBasic, ParseExperience, ParseSkills, ScoreOutput
from app.core.config import Settings, get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)
Output = TypeVar("Output", bound=BaseModel)
TIMEOUT_SECONDS = 60
MAX_OUTPUT_TOKENS = 4096
TRANSIENT_STATUS = {429, 500, 502, 503, 504, 529}


class LLMError(AppError):
    def __init__(self) -> None:
        super().__init__("LLM_UNAVAILABLE", "Không gọi được dịch vụ xử lý AI.", 503)


class LLMConfigurationError(AppError):
    def __init__(self) -> None:
        super().__init__("LLM_CONFIGURATION_ERROR", "Cấu hình dịch vụ AI chưa hợp lệ.", 500)


class LLMValidationError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "LLM_INVALID_OUTPUT", "Kết quả AI không đúng định dạng sau khi thử lại.", 502
        )


@runtime_checkable
class LLMClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[Output],
        temperature: float = 0,
    ) -> Output: ...


@dataclass(frozen=True)
class _Completion:
    data: Any = field(repr=False)
    input_tokens: int | None = None
    output_tokens: int | None = None


def _tokens(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


class _BaseLLM:
    provider = ""
    model = ""

    def _metadata(
        self,
        outcome: str,
        start: float,
        completion: _Completion | None = None,
        **metadata: int,
    ) -> None:
        logger.info(
            "LLM request",
            extra={
                "provider": self.provider,
                "model": self.model,
                "input_tokens": completion.input_tokens if completion else None,
                "output_tokens": completion.output_tokens if completion else None,
                "duration_ms": round((time.perf_counter() - start) * 1000, 3),
                "outcome": outcome,
                **metadata,
            },
        )

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[Output],
        temperature: float = 0,
    ) -> Output:
        if not math.isfinite(temperature) or not 0 <= temperature <= 1:
            raise LLMConfigurationError()
        request_system = system
        for attempt in range(2):
            start = time.perf_counter()
            try:
                completion = self._generate(request_system, user, schema, temperature)
            except LLMError:
                self._metadata("provider_error", start, validation_attempt=attempt + 1)
                raise
            try:
                if isinstance(completion.data, str):
                    result = schema.model_validate_json(completion.data, strict=True)
                else:
                    result = schema.model_validate(completion.data, strict=True)
            except ValidationError as exc:
                self._metadata("invalid_output", start, completion, validation_attempt=attempt + 1)
                # Error messages, locations, input and context can all echo provider/CV text.
                # Send only Pydantic error codes, never the rejected output or raw exception.
                codes = [
                    error["type"]
                    for error in exc.errors(
                        include_input=False, include_context=False, include_url=False
                    )
                ][:10]
                request_system = (
                    system
                    + "\nKết quả trước không đúng schema. Lỗi validate (chỉ mã lỗi): "
                    + json.dumps(codes)
                    + ". Hãy trả lại JSON đúng schema, không thêm trường hoặc bình luận."
                )
            else:
                self._metadata("ok", start, completion, validation_attempt=attempt + 1)
                return result
        raise LLMValidationError() from None

    def _generate(
        self, system: str, user: str, schema: type[BaseModel], temperature: float
    ) -> _Completion:
        raise NotImplementedError


def _fold(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
        if not unicodedata.combining(char)
    )


def _line_value(text: str, labels: str) -> str | None:
    match = re.search(rf"(?im)^[^\S\r\n]*(?:{labels})[^\S\r\n]*:[^\S\r\n]*([^\r\n]*)", text)
    return (match[1].strip() or None) if match else None


class FakeLLM(_BaseLLM):
    """Offline fixture heuristic, not an assessment of real candidate quality."""

    provider = "fake"
    model = "fake-v1"

    def _generate(
        self, system: str, user: str, schema: type[BaseModel], temperature: float
    ) -> _Completion:
        try:
            payload = json.loads(user)
            if not isinstance(payload, dict):
                raise ValueError
            if schema is ScoreOutput:
                text = payload["anonymized_text"]
                criteria = []
                for kind, key in (("must", "must_have"), ("nice", "nice_to_have")):
                    for criterion in payload[key]:
                        # Whole phrase, with word boundaries, case/accent-insensitive.
                        match = re.search(
                            r"(?<!\w)" + re.escape(_fold(criterion)) + r"(?!\w)", _fold(text)
                        )
                        evidence = None
                        if match:
                            # Search original text too, so evidence is always an exact substring.
                            for line in text.splitlines():
                                if re.search(
                                    r"(?<!\w)" + re.escape(_fold(criterion)) + r"(?!\w)",
                                    _fold(line),
                                ):
                                    evidence = " ".join(line.split()[:20])
                                    if evidence not in text:
                                        evidence = line.strip() if len(line.split()) <= 20 else None
                                    break
                        criteria.append(
                            {
                                "criterion": criterion,
                                "kind": kind,
                                "result": "met" if match else "not_met",
                                "evidence": evidence,
                            }
                        )
                missing = any(c["kind"] == "must" and c["result"] == "not_met" for c in criteria)
                data = {
                    "criteria": criteria,
                    "reasons": [
                        "Đối chiếu từ khoá kỹ năng với từng tiêu chí đã cung cấp.",
                        "Cần HR kiểm tra lại kinh nghiệm và mức độ phù hợp.",
                    ],
                    "flags": ["missing_must_have"] if missing else [],
                }
            else:
                text = payload["cv_text"]
                if schema is ParseBasic:
                    years = _line_value(text, "Số năm kinh nghiệm|Years of experience")
                    number = re.match(r"\d+(?:[.,]\d+)?", years or "")
                    languages = _line_value(text, "Ngôn ngữ|Languages?")
                    data = {
                        "full_name": _line_value(text, "Họ tên|Họ và tên|Full name|Name"),
                        "current_title": _line_value(
                            text, "Vị trí hiện tại|Chức danh|Current title"
                        ),
                        "location": _line_value(text, "Địa điểm|Location"),
                        "years_experience": float(number[0].replace(",", ".")) if number else None,
                        "languages": [v.strip() for v in re.split("[,;]", languages) if v.strip()]
                        if languages
                        else [],
                    }
                elif schema is ParseExperience:
                    # No inference of company, chronology or education from prose in the fake.
                    data = {"experiences": [], "education": []}
                elif schema is ParseSkills:
                    skills = _line_value(text, "Kỹ năng|Skills?")
                    data = {
                        "skills": [v.strip() for v in re.split("[,;]", skills) if v.strip()]
                        if skills
                        else []
                    }
                else:
                    raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
            raise LLMError() from None
        return _Completion(data)


class _HTTPLLM(_BaseLLM):
    def __init__(
        self,
        *,
        model: str,
        api_key: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,199}", model) is None:
            raise LLMConfigurationError()
        self.model = model
        self._key = SecretStr(api_key)
        self._transport = transport

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(3):
            start = time.perf_counter()
            retry_outcome = "retry_network"
            try:
                # Each invocation owns and closes its client, including error/retry paths.
                with httpx.Client(
                    timeout=TIMEOUT_SECONDS,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client:
                    response = client.post(url, headers=headers, json=body)
                if response.status_code in TRANSIENT_STATUS:
                    retry_outcome = "retry_http"
                elif not response.is_success:
                    raise LLMError()
                else:
                    try:
                        data = response.json()
                        if not isinstance(data, dict):
                            raise ValueError
                        return data
                    except (ValueError, RecursionError):
                        raise LLMError() from None
            except httpx.TransportError:
                pass
            if attempt == 2:
                raise LLMError() from None
            self._metadata(retry_outcome, start, transport_attempt=attempt + 1)
            time.sleep(2**attempt)
        raise LLMError()


class AnthropicLLM(_HTTPLLM):
    provider = "anthropic"

    def __init__(self, *, model: str, api_key: str, transport=None) -> None:
        super().__init__(model=model, api_key=api_key, transport=transport)
        if not api_key.strip():
            raise LLMConfigurationError()

    def _generate(self, system, user, schema, temperature) -> _Completion:
        data = self._post(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": self._key.get_secret_value(), "anthropic-version": "2023-06-01"},
            {
                "model": self.model,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "temperature": temperature,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "tools": [
                    {
                        "name": "structured_output",
                        "description": "Trả kết quả JSON theo schema, không thực hiện hành động.",
                        "input_schema": schema.model_json_schema(),
                    }
                ],
                "tool_choice": {"type": "tool", "name": "structured_output"},
            },
        )
        try:
            if data["stop_reason"] != "tool_use":
                raise ValueError
            blocks = [
                item
                for item in data["content"]
                if item["type"] == "tool_use" and item["name"] == "structured_output"
            ]
            if len(blocks) != 1:
                raise ValueError
            usage = data.get("usage", {})
            return _Completion(
                blocks[0]["input"],
                _tokens(usage.get("input_tokens")),
                _tokens(usage.get("output_tokens")),
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise LLMError() from None


class OpenAILLM(_HTTPLLM):
    provider = "openai"

    def __init__(self, *, model: str, api_key: str, transport=None) -> None:
        super().__init__(model=model, api_key=api_key, transport=transport)
        if not api_key.strip():
            raise LLMConfigurationError()

    def _generate(self, system, user, schema, temperature) -> _Completion:
        data = self._post(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": "Bearer " + self._key.get_secret_value()},
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_completion_tokens": MAX_OUTPUT_TOKENS,
                "store": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "strict": True,
                        "schema": schema.model_json_schema(),
                    },
                },
            },
        )
        try:
            choice = data["choices"][0]
            if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
                raise ValueError
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise ValueError
            usage = data.get("usage", {})
            return _Completion(
                content,
                _tokens(usage.get("prompt_tokens")),
                _tokens(usage.get("completion_tokens")),
            )
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise LLMError() from None


class OllamaLLM(_HTTPLLM):
    provider = "ollama"

    def __init__(
        self, *, model: str, base_url: str = "http://localhost:11434", transport=None
    ) -> None:
        super().__init__(model=model, transport=transport)
        try:
            parsed = urlsplit(base_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
                or parsed.port == 0
            ):
                raise ValueError
        except ValueError:
            raise LLMConfigurationError() from None
        self._base_url = base_url.rstrip("/")

    def _generate(self, system, user, schema, temperature) -> _Completion:
        data = self._post(
            self._base_url + "/api/chat",
            {},
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": schema.model_json_schema(),
                "stream": False,
                "options": {"temperature": temperature, "num_predict": MAX_OUTPUT_TOKENS},
            },
        )
        try:
            if data["done"] is not True or data.get("done_reason") == "length":
                raise ValueError
            content = data["message"]["content"]
            if not isinstance(content, str):
                raise ValueError
            return _Completion(
                content, _tokens(data.get("prompt_eval_count")), _tokens(data.get("eval_count"))
            )
        except (KeyError, TypeError, ValueError):
            raise LLMError() from None


def get_llm_client(
    settings: Settings | None = None, *, transport: httpx.BaseTransport | None = None
) -> LLMClient:
    settings = settings or get_settings()
    match settings.llm_provider:
        case "fake":
            return FakeLLM()
        case "anthropic":
            return AnthropicLLM(
                model=settings.llm_model,
                api_key=settings.anthropic_api_key.get_secret_value(),
                transport=transport,
            )
        case "openai":
            return OpenAILLM(
                model=settings.llm_model,
                api_key=settings.openai_api_key.get_secret_value(),
                transport=transport,
            )
        case "ollama":
            return OllamaLLM(
                model=settings.llm_model, base_url=settings.ollama_base_url, transport=transport
            )
        case _:
            raise LLMConfigurationError()
