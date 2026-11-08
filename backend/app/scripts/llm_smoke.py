"""Manual opt-in provider smoke using only synthetic, contact-free text."""

import argparse
import json
from collections.abc import Sequence

from pydantic import ValidationError

from app.ai.llm import get_llm_client
from app.ai.prompts import load_prompt
from app.ai.schemas import ParseBasic, ParseExperience, ParseSkills, ScoreOutput
from app.core.config import Settings
from app.core.errors import AppError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Thử dịch vụ AI bằng dữ liệu giả, không dùng CV thật."
    )
    parser.add_argument(
        "--provider", choices=["fake", "anthropic", "openai", "ollama"], default="fake"
    )
    parser.add_argument("--model", help="Model id; mặc định lấy LLM_MODEL từ môi trường.")
    args = parser.parse_args(argv)
    try:
        settings = Settings()
        settings = settings.model_copy(
            update={"llm_provider": args.provider, "llm_model": args.model or settings.llm_model}
        )
        client = get_llm_client(settings)
        text = "Họ tên: Ứng viên Mô Phỏng\nKỹ năng: Python, SQL\nSố năm kinh nghiệm: 3"
        tasks = (
            ("parse_cv_basic", ParseBasic),
            ("parse_cv_experience", ParseExperience),
            ("parse_cv_skills", ParseSkills),
            ("score_cv", ScoreOutput),
        )
        for task, schema in tasks:
            prompt = load_prompt(task).render(
                text=text,
                anonymized_text="[TÊN]\nKỹ năng: Python, SQL\nSố năm kinh nghiệm: 3",
                job_title="Lập trình viên mô phỏng",
                job_description="Dự án giả để thử kết nối.",
                must_have=["Python"],
                nice_to_have=["SQL"],
            )
            client.complete_json(system=prompt.system, user=prompt.user, schema=schema)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "provider": args.provider,
                    "model": client.model,
                    "prompt_version": "v1",
                    "tasks": [task for task, _ in tasks],
                },
                ensure_ascii=False,
            )
        )
    except AppError as exc:
        print(
            json.dumps(
                {"status": "error", "code": exc.code, "message": exc.message}, ensure_ascii=False
            )
        )
        return 1
    except ValidationError:
        print('{"status": "error", "code": "INVALID_SETTINGS"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
