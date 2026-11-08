import json
import logging
from unittest.mock import Mock

import httpx
import pytest

from app.ai import llm
from app.ai.llm import (
    AnthropicLLM,
    FakeLLM,
    LLMClient,
    LLMConfigurationError,
    LLMError,
    LLMValidationError,
    OllamaLLM,
    OpenAILLM,
    get_llm_client,
)
from app.ai.prompts import load_prompt
from app.ai.schemas import ParseBasic, ParseExperience, ParseSkills, ScoreOutput
from app.core.config import Settings, get_settings
from app.core.logging import JsonFormatter, PiiFilter
from app.scripts import llm_smoke

PROVIDERS = ["anthropic", "openai", "ollama"]
INPUT_MARKER = "SYNTHETIC_PRIVATE_CV_MARKER"
OUTPUT_MARKER = "SYNTHETIC_PROVIDER_OUTPUT_MARKER"
KEY_MARKER = "synthetic-key-for-adapter-tests"


def settings(provider):
    return Settings(
        _env_file=None,
        llm_provider=provider,
        llm_model="synthetic-model-v1",
        anthropic_api_key=KEY_MARKER,
        openai_api_key=KEY_MARKER,
        ollama_base_url="http://localhost:11434",
    )


def envelope(provider, output):
    content = output if isinstance(output, str) else json.dumps(output)
    if provider == "anthropic":
        return {
            "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "name": "structured_output", "input": output}],
            "usage": {"input_tokens": 17, "output_tokens": 9},
        }
    if provider == "openai":
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 17, "completion_tokens": 9},
        }
    return {
        "done": True,
        "done_reason": "stop",
        "message": {"content": content},
        "prompt_eval_count": 17,
        "eval_count": 9,
    }


def invoke(client):
    return client.complete_json(
        system="Chỉ trả JSON. " + INPUT_MARKER, user=INPUT_MARKER, schema=ParseSkills
    )


@pytest.mark.parametrize(
    "provider,adapter",
    [("fake", FakeLLM), ("anthropic", AnthropicLLM), ("openai", OpenAILLM), ("ollama", OllamaLLM)],
)
def test_factory_selects_adapter_without_connecting(provider, adapter):
    client = get_llm_client(settings(provider))
    assert isinstance(client, adapter)
    assert isinstance(client, LLMClient)
    assert KEY_MARKER not in repr(client)


def test_factory_reads_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "synthetic-environment-model")
    get_settings.cache_clear()
    try:
        client = get_llm_client()
        assert isinstance(client, OllamaLLM)
        assert client.model == "synthetic-environment-model"
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_real_adapters_require_an_explicit_model(provider):
    with pytest.raises(LLMConfigurationError):
        get_llm_client(settings(provider).model_copy(update={"llm_model": ""}))


@pytest.mark.parametrize("adapter", [AnthropicLLM, OpenAILLM])
def test_cloud_adapters_require_key(adapter):
    with pytest.raises(LLMConfigurationError):
        adapter(model="synthetic-v1", api_key=" ")


@pytest.mark.parametrize(
    "url",
    [
        "file:///x",
        "http://user:secret@localhost:11434",
        "http://localhost/cv",
        "http://localhost?cv=secret",
        "http://localhost#secret",
        "http://localhost:0",
        "http://localhost:bad",
    ],
)
def test_ollama_base_url_rejects_credentials_and_input_in_urls(url):
    with pytest.raises(LLMConfigurationError):
        OllamaLLM(model="synthetic-v1", base_url=url)


def test_fake_parse_uses_real_templates_and_is_deterministic():
    client = FakeLLM()
    text = (
        "Họ tên: Ứng viên Mô Phỏng\nVị trí hiện tại: Lập trình viên giả\n"
        "Địa điểm: Khu vực mô phỏng\nSố năm kinh nghiệm: 3,5 năm\n"
        "Ngôn ngữ: Tiếng Việt, Tiếng Anh\nKỹ năng: Python; SQL; JS; javascript"
    )
    outputs = {}
    for task, schema in (
        ("parse_cv_basic", ParseBasic),
        ("parse_cv_experience", ParseExperience),
        ("parse_cv_skills", ParseSkills),
    ):
        prompt = load_prompt(task).render(text=text)
        result = client.complete_json(system=prompt.system, user=prompt.user, schema=schema)
        assert result == client.complete_json(system=prompt.system, user=prompt.user, schema=schema)
        assert schema.model_validate(result.model_dump()) == result
        outputs[task] = result
    assert outputs["parse_cv_basic"].full_name == "Ứng viên Mô Phỏng"
    assert outputs["parse_cv_basic"].years_experience == 3.5
    assert outputs["parse_cv_basic"].languages == ["Tiếng Việt", "Tiếng Anh"]
    assert outputs["parse_cv_skills"].skills == ["python", "sql", "javascript"]
    assert outputs["parse_cv_experience"].experiences == []


def test_fake_does_not_infer_missing_basic_information():
    prompt = load_prompt("parse_cv_basic").render(text="Nội dung giả không có thông tin.")
    result = FakeLLM().complete_json(system=prompt.system, user=prompt.user, schema=ParseBasic)
    assert result.full_name is result.years_experience is result.location is None
    assert result.languages == []


def test_fake_empty_label_does_not_consume_the_following_section():
    prompt = load_prompt("parse_cv_basic").render(
        text="Họ tên:   \nKỹ năng: Python\nĐịa điểm:\nSố năm kinh nghiệm: 3"
    )
    result = FakeLLM().complete_json(system=prompt.system, user=prompt.user, schema=ParseBasic)
    assert result.full_name is result.location is None
    assert result.years_experience == 3
    prompt = load_prompt("parse_cv_skills").render(text="Kỹ năng:\nKinh nghiệm: Dữ liệu giả")
    result = FakeLLM().complete_json(system=prompt.system, user=prompt.user, schema=ParseSkills)
    assert result.skills == []


@pytest.mark.parametrize("provider", PROVIDERS)
def test_transport_and_validation_retries_are_bounded_together(provider, monkeypatch):
    requests = []
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)

    def handler(request):
        requests.append(request)
        if len(requests) % 3:
            return httpx.Response(429, text=OUTPUT_MARKER)
        return httpx.Response(200, json=envelope(provider, {"skills": 42}))

    with pytest.raises(LLMValidationError):
        invoke(get_llm_client(settings(provider), transport=httpx.MockTransport(handler)))
    assert len(requests) == 6


@pytest.mark.parametrize("provider", PROVIDERS)
def test_non_json_provider_envelope_fails_without_echo_or_retry(provider, caplog):
    requests = []
    caplog.set_level(logging.INFO)

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=OUTPUT_MARKER)

    with pytest.raises(LLMError) as caught:
        invoke(get_llm_client(settings(provider), transport=httpx.MockTransport(handler)))
    assert len(requests) == 1
    assert OUTPUT_MARKER not in str(caught.value) and OUTPUT_MARKER not in caplog.text


def test_fake_score_only_reads_cv_and_keeps_criteria_order_and_evidence():
    text = "[TÊN]\nKỹ năng: PYTHON, PostgreSQL, quản lý dự án\nJavaScript"
    prompt = load_prompt("score_cv").render(
        anonymized_text=text,
        job_title="Java, Go",
        job_description="Cần Java và Go",
        must_have=["Python", "Java", "quan ly du an"],
        nice_to_have=["Go", "PostgreSQL"],
    )
    result = FakeLLM().complete_json(system=prompt.system, user=prompt.user, schema=ScoreOutput)
    assert [c.result for c in result.criteria] == ["met", "not_met", "met", "not_met", "met"]
    assert [c.kind for c in result.criteria] == ["must", "must", "must", "nice", "nice"]
    assert [c.criterion for c in result.criteria] == [
        "Python",
        "Java",
        "quan ly du an",
        "Go",
        "PostgreSQL",
    ]
    for criterion in result.criteria:
        assert criterion.evidence is None or criterion.evidence in text
    assert result.flags == ["missing_must_have"]
    assert len(result.reasons) in {2, 3}
    assert "[TÊN]" not in " ".join(result.reasons)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_provider_request_schema_auth_timeout_and_token_metadata(provider, caplog):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=envelope(provider, {"skills": ["Python"]}))

    caplog.set_level(logging.INFO)
    client = get_llm_client(settings(provider), transport=httpx.MockTransport(handler))
    result = invoke(client)
    assert result.skills == ["python"]
    assert len(requests) == 1
    request = requests[0]
    assert set(request.extensions["timeout"].values()) == {60}
    body = json.loads(request.content)
    assert body["model"] == "synthetic-model-v1"
    assert body["temperature"] == 0 if provider != "ollama" else body["options"]["temperature"] == 0
    if provider == "anthropic":
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == KEY_MARKER
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert body["tools"][0]["input_schema"] == ParseSkills.model_json_schema()
        assert body["tool_choice"] == {"type": "tool", "name": "structured_output"}
        assert body["system"].endswith(INPUT_MARKER)
        assert body["max_tokens"] == 4096
    elif provider == "openai":
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer " + KEY_MARKER
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["response_format"]["json_schema"]["schema"] == ParseSkills.model_json_schema()
        assert body["store"] is False
        assert body["max_completion_tokens"] == 4096
    else:
        assert str(request.url) == "http://localhost:11434/api/chat"
        assert body["format"] == ParseSkills.model_json_schema()
        assert body["stream"] is False
        assert body["options"]["num_predict"] == 4096
    record = next(r for r in caplog.records if r.name == "app.ai.llm" and r.outcome == "ok")
    assert record.input_tokens == 17 and record.output_tokens == 9
    assert record.duration_ms >= 0
    assert record.model == "synthetic-model-v1"
    assert INPUT_MARKER not in caplog.text


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("repair_succeeds", [True, False])
def test_invalid_schema_is_repaired_once_without_echoing_output(provider, repair_succeeds, caplog):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        output = (
            {"skills": ["Python"]}
            if repair_succeeds and len(requests) == 2
            else {OUTPUT_MARKER: INPUT_MARKER}
        )
        return httpx.Response(200, json=envelope(provider, output))

    caplog.set_level(logging.INFO)
    client = get_llm_client(settings(provider), transport=httpx.MockTransport(handler))
    if repair_succeeds:
        assert invoke(client).skills == ["python"]
    else:
        with pytest.raises(LLMValidationError) as caught:
            invoke(client)
        assert INPUT_MARKER not in str(caught.value)
        assert OUTPUT_MARKER not in str(caught.value)
    assert len(requests) == 2
    second = requests[1]
    system = second["system"] if provider == "anthropic" else second["messages"][0]["content"]
    assert "missing" in system and "extra_forbidden" in system
    assert "Lỗi validate" in system
    assert OUTPUT_MARKER not in json.dumps(second)
    assert INPUT_MARKER not in caplog.text and OUTPUT_MARKER not in caplog.text


@pytest.mark.parametrize("provider", ["openai", "ollama"])
def test_invalid_json_gets_one_repair(provider):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=envelope(provider, "not JSON " + OUTPUT_MARKER))

    client = get_llm_client(settings(provider), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMValidationError):
        invoke(client)
    assert len(requests) == 2
    assert "json_invalid" in requests[1].content.decode()
    assert OUTPUT_MARKER not in requests[1].content.decode()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("failure", [429, 503, 529, "timeout", "connect"])
def test_transient_errors_retry_twice_with_backoff(provider, failure, monkeypatch):
    requests = []
    sleep = Mock()
    monkeypatch.setattr(llm.time, "sleep", sleep)

    def handler(request):
        requests.append(request)
        if len(requests) < 3:
            if failure == "timeout":
                raise httpx.ReadTimeout(OUTPUT_MARKER, request=request)
            if failure == "connect":
                raise httpx.ConnectError(OUTPUT_MARKER, request=request)
            return httpx.Response(failure, json={"error": OUTPUT_MARKER})
        return httpx.Response(200, json=envelope(provider, {"skills": []}))

    client = get_llm_client(settings(provider), transport=httpx.MockTransport(handler))
    assert invoke(client).skills == []
    assert len(requests) == 3
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]
    assert len({request.content for request in requests}) == 1


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("failure", [429, "timeout"])
def test_exhausted_retries_stop_at_three_and_do_not_leak(provider, failure, caplog, monkeypatch):
    requests = []
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    caplog.set_level(logging.INFO)

    def handler(request):
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout(OUTPUT_MARKER + INPUT_MARKER + KEY_MARKER, request=request)
        return httpx.Response(429, json={"error": OUTPUT_MARKER + INPUT_MARKER + KEY_MARKER})

    client = get_llm_client(settings(provider), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError) as caught:
        invoke(client)
    assert len(requests) == 3
    for marker in (INPUT_MARKER, OUTPUT_MARKER, KEY_MARKER):
        assert marker not in caplog.text
        assert marker not in str(caught.value)


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 302])
def test_permanent_errors_and_redirects_do_not_retry(provider, status, monkeypatch):
    requests = []
    sleep = Mock()
    monkeypatch.setattr(llm.time, "sleep", sleep)

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, headers={"location": "https://untrusted.invalid"}, text=OUTPUT_MARKER
        )

    with pytest.raises(LLMError):
        invoke(get_llm_client(settings(provider), transport=httpx.MockTransport(handler)))
    assert len(requests) == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("output", [{}, [], {"usage": None}])
def test_malformed_provider_envelope_is_a_safe_error(provider, output):
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=output))
    with pytest.raises(LLMError):
        invoke(get_llm_client(settings(provider), transport=transport))


@pytest.mark.parametrize("provider", PROVIDERS)
def test_truncated_or_refused_completion_is_not_accepted(provider):
    output = envelope(provider, {"skills": []})
    if provider == "anthropic":
        output["stop_reason"] = "max_tokens"
    elif provider == "openai":
        output["choices"][0]["finish_reason"] = "length"
    else:
        output["done_reason"] = "length"
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=output))
    with pytest.raises(LLMError):
        invoke(get_llm_client(settings(provider), transport=transport))


def test_openai_refusal_is_a_safe_error():
    output = envelope("openai", {"skills": []})
    output["choices"][0]["message"]["refusal"] = OUTPUT_MARKER
    with pytest.raises(LLMError):
        invoke(
            get_llm_client(
                settings("openai"),
                transport=httpx.MockTransport(lambda _: httpx.Response(200, json=output)),
            )
        )


def test_fake_logs_no_input_even_without_pii_filter(caplog):
    caplog.set_level(logging.INFO, logger="app.ai.llm")
    prompt = load_prompt("parse_cv_basic").render(text="Họ tên: " + INPUT_MARKER)
    FakeLLM().complete_json(system=prompt.system, user=prompt.user, schema=ParseBasic)
    assert INPUT_MARKER not in caplog.text
    record = next(r for r in caplog.records if r.name == "app.ai.llm")
    assert record.input_tokens is record.output_tokens is None
    PiiFilter().filter(record)
    rendered = json.loads(JsonFormatter().format(record))
    assert rendered["provider"] == "fake"
    assert rendered["model"] == "fake-v1"
    assert INPUT_MARKER not in json.dumps(rendered)


def test_smoke_fake_runs_all_four_tasks_and_prints_only_metadata(capsys):
    assert llm_smoke.main(["--provider", "fake"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok" and output["provider"] == "fake"
    assert len(output["tasks"]) == 4 and output["prompt_version"] == "v1"
    assert "Ứng viên" not in json.dumps(output, ensure_ascii=False)


def test_smoke_cloud_can_be_exercised_with_http_mock(monkeypatch, capsys):
    def handler(request):
        schema_name = json.loads(request.content)["tools"][0]["input_schema"]["title"]
        result = {
            "ParseBasic": {
                "full_name": None,
                "current_title": None,
                "location": None,
                "years_experience": None,
                "languages": [],
            },
            "ParseExperience": {"experiences": [], "education": []},
            "ParseSkills": {"skills": []},
            "ScoreOutput": {"criteria": [], "reasons": ["Giả một.", "Giả hai."], "flags": []},
        }[schema_name]
        return httpx.Response(200, json=envelope("anthropic", result))

    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY_MARKER)
    monkeypatch.setenv("LLM_MODEL", "synthetic-model-v1")
    monkeypatch.setattr(
        llm_smoke,
        "get_llm_client",
        lambda settings: get_llm_client(settings, transport=httpx.MockTransport(handler)),
    )
    assert llm_smoke.main(["--provider", "anthropic"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_smoke_missing_key_fails_cleanly_without_connecting(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert llm_smoke.main(["--provider", "anthropic", "--model", "synthetic-v1"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["code"] == "LLM_CONFIGURATION_ERROR"
