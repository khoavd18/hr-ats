import json
import logging
from threading import Barrier, Lock

import pytest

from app.ai.llm import FakeLLM, LLMValidationError
from app.ai.parse import parse_cv
from app.ai.schemas import ParseBasic, ParseExperience, ParseSkills

TEXT = "Họ tên: Nhân vật giả\nChức danh: Lập trình viên\nKỹ năng: JS, Python\nSố năm kinh nghiệm: 3"


def test_three_parts_run_concurrently_with_real_prompts_and_merge():
    barrier = Barrier(3)
    lock = Lock()
    calls = []

    class ParallelLLM(FakeLLM):
        def complete_json(self, **kwargs):
            with lock:
                calls.append(kwargs)
            # A sequential implementation breaks this barrier, without timing assertions.
            barrier.wait(timeout=5)
            return super().complete_json(**kwargs)

    result = parse_cv(TEXT, client=ParallelLLM())
    assert {call["schema"] for call in calls} == {ParseBasic, ParseExperience, ParseSkills}
    assert all(call["temperature"] == 0 for call in calls)
    assert all(json.loads(call["user"])["cv_text"] == TEXT for call in calls)
    assert result.parsed.full_name == "Nhân vật giả"
    assert result.parsed.skills == ["javascript", "python"]
    assert result.parsed.education == result.parsed.experiences == []
    assert result.model == "fake-v1" and result.prompt_version == "v1"
    assert "Nhân vật giả" not in repr(result)


@pytest.mark.parametrize("failed_part", [ParseBasic, ParseExperience, ParseSkills])
def test_one_failed_part_does_not_return_partial_cv(failed_part):
    class FailingLLM(FakeLLM):
        def complete_json(self, **kwargs):
            if kwargs["schema"] is failed_part:
                raise LLMValidationError()
            return super().complete_json(**kwargs)

    with pytest.raises(LLMValidationError):
        parse_cv(TEXT, client=FailingLLM())


def test_adapter_retries_invalid_part_once_then_fails_safely(caplog):
    caplog.set_level(logging.INFO, logger="app.ai.llm")

    class InvalidLLM(FakeLLM):
        attempts = 0

        def _generate(self, system, user, schema, temperature):
            result = super()._generate(system, user, schema, temperature)
            if schema is ParseSkills:
                self.attempts += 1
                return type(result)(data={"skills": "synthetic-invalid-output"})
            return result

    client = InvalidLLM()
    with pytest.raises(LLMValidationError):
        parse_cv(TEXT, client=client)
    assert client.attempts == 2
    assert TEXT not in caplog.text and "synthetic-invalid-output" not in caplog.text


def test_missing_data_remains_null_and_empty():
    result = parse_cv("CV giả chưa có thông tin")
    assert result.parsed.full_name is None
    assert result.parsed.years_experience is None
    assert result.parsed.skills == result.parsed.languages == []
