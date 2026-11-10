"""Evaluate CV parse accuracy against ground-truth labels.

Metrics (per field):
  - full_name, email, phone: exact match after normalisation
  - skills: token-level F1 (casefold, sort)
  - current_title, location, years_experience: exact match / absolute error

Usage:
    # Offline (no network, synthetic data only)
    uv run python eval/run_parse_eval.py --provider fake --data synthetic

    # Real provider with public dataset dir
    uv run python eval/run_parse_eval.py --provider anthropic --model claude-opus-5-5 \\
        --data dir:var/datasets/resume-dataset --prompt-version 1
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.extract import ExtractionError, extract_text  # noqa: E402
from app.ai.llm import FakeLLM, get_llm_client  # noqa: E402
from app.ai.parse import parse_cv  # noqa: E402
from app.ai.redact import redact_contacts  # noqa: E402

from eval.schemas import CVLabel, JobDataset  # noqa: E402

SAMPLE_DIR = ROOT / "data" / "sample_cvs"
REPORTS_DIR = ROOT / "eval" / "reports"


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _norm(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _phone_norm(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _skill_tokens(skills: list[str]) -> set[str]:
    tokens: set[str] = set()
    for s in skills:
        tokens.update(_norm(s).split())
    return tokens


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _exact(predicted: Any, expected: Any) -> int:
    return 1 if str(predicted) == str(expected) else 0


def _f1_set(pred: set[str], true: set[str]) -> float:
    if not pred and not true:
        return 1.0
    if not pred or not true:
        return 0.0
    precision = len(pred & true) / len(pred)
    recall = len(pred & true) / len(true)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_synthetic(data_dir: Path) -> tuple[list[CVLabel], JobDataset]:
    jobs_path = data_dir / "jobs.json"
    if not jobs_path.exists():
        sys.exit(f"Không tìm thấy {jobs_path}. Chạy generate_synthetic_cvs.py trước.")
    jobs = JobDataset.model_validate_json(jobs_path.read_text(encoding="utf-8"))
    labels: list[CVLabel] = []
    for p in sorted(data_dir.glob("cv_*.json")):
        labels.append(CVLabel.model_validate_json(p.read_text(encoding="utf-8")))
    if not labels:
        sys.exit(f"Không tìm thấy CV trong {data_dir}")
    return labels, jobs


def _load_dir(data_dir: Path) -> list[dict]:
    """Load CV files from a directory (no ground-truth labels — text extraction only)."""
    files = sorted(
        p
        for ext in ("*.pdf", "*.docx", "*.png", "*.jpg", "*.jpeg")
        for p in data_dir.glob(ext)
    )
    if not files:
        sys.exit(f"Không tìm thấy PDF/DOCX trong {data_dir}")
    return [{"path": p} for p in files]


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def _eval_cv_label(
    label: CVLabel,
    cv_path: Path,
    client: Any,
) -> dict:
    """Extract, redact, parse one CV and compare against its label."""
    try:
        data = cv_path.read_bytes()
        mime = "application/pdf" if cv_path.suffix == ".pdf" else (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        result = extract_text(data, mime)
        text, _, _ = redact_contacts(result.text)
        parsed = parse_cv(text, client=client)
        p = parsed.parsed

        name_match = _exact(_norm(p.full_name), _norm(label.full_name))
        title_match = _exact(_norm(p.current_title), _norm(label.current_title))
        loc_match = _exact(_norm(p.location), _norm(label.location))
        yoe_match = _exact(str(p.years_experience), str(label.years_experience))
        skills_f1 = _f1_set(
            _skill_tokens(p.skills or []),
            _skill_tokens(label.skills),
        )
        return {
            "id": label.id,
            "ok": True,
            "name_match": name_match,
            "title_match": title_match,
            "location_match": loc_match,
            "yoe_match": yoe_match,
            "skills_f1": skills_f1,
            "predicted_name": p.full_name,
            "expected_name": label.full_name,
            "predicted_skills": sorted(p.skills or []),
            "expected_skills": sorted(label.skills),
            "model": parsed.model,
            "prompt_version": parsed.prompt_version,
        }
    except (ExtractionError, Exception) as exc:
        return {"id": label.id, "ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _aggregate(results: list[dict]) -> dict:
    ok = [r for r in results if r.get("ok")]
    n = len(ok)
    if not n:
        return {"n": 0, "failed": len(results)}
    return {
        "n": n,
        "failed": len(results) - n,
        "name_acc": sum(r["name_match"] for r in ok) / n,
        "title_acc": sum(r["title_match"] for r in ok) / n,
        "location_acc": sum(r["location_match"] for r in ok) / n,
        "yoe_acc": sum(r["yoe_match"] for r in ok) / n,
        "skills_f1": sum(r["skills_f1"] for r in ok) / n,
    }


def _write_report(
    results: list[dict],
    agg: dict,
    provider: str,
    model: str,
    prompt_version: str,
    data_source: str,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = model.replace("/", "-").replace(":", "-")
    path = REPORTS_DIR / f"{today}-parse-{slug}-v{prompt_version}.md"

    errors = [r for r in results if not r.get("ok")]
    # Up to 10 representative wrong predictions
    wrong = [
        r
        for r in results
        if r.get("ok") and (
            r["name_match"] == 0 or r["title_match"] == 0 or r["skills_f1"] < 0.5
        )
    ][:10]

    lines = [
        "# Báo cáo đánh giá Parse CV",
        "",
        "| Thông số | Giá trị |",
        "|---|---|",
        f"| Ngày | {today} |",
        f"| Provider | {provider} |",
        f"| Model | {model} |",
        f"| Prompt version | v{prompt_version} |",
        f"| Nguồn dữ liệu | {data_source} |",
        "",
        "## Chỉ số tổng hợp",
        "",
        "| Trường | Độ chính xác |",
        "|---|---|",
        f"| Họ tên (exact match) | {agg.get('name_acc', 0):.1%} |",
        f"| Chức danh (exact match) | {agg.get('title_acc', 0):.1%} |",
        f"| Địa điểm (exact match) | {agg.get('location_acc', 0):.1%} |",
        f"| Số năm KN (exact match) | {agg.get('yoe_acc', 0):.1%} |",
        f"| Kỹ năng (F1) | {agg.get('skills_f1', 0):.3f} |",
        "",
        f"Tổng: {agg.get('n', 0)} CV, lỗi: {agg.get('failed', 0)}",
        "",
    ]
    if errors:
        lines += [
            "## Lỗi trích xuất / parse",
            "",
            "| ID | Lỗi |",
            "|---|---|",
        ]
        for r in errors:
            lines.append(f"| {r['id']} | {r.get('error', '')} |")
        lines.append("")

    if wrong:
        lines += [
            "## 10 ví dụ sai tiêu biểu (đã ẩn danh)",
            "",
            "| ID | Trường | Dự đoán | Nhãn thật |",
            "|---|---|---|---|",
        ]
        for r in wrong:
            if r["name_match"] == 0:
                # Anonymise: show only first token of predicted name
                pred_first = (_norm(r.get("predicted_name")) or "").split()
                pred_tok = pred_first[0] if pred_first else "(trống)"
                exp_first = _norm(r.get("expected_name", "")).split()
                exp_tok = exp_first[0] if exp_first else ""
                lines.append(f"| {r['id']} | Họ tên | {pred_tok} | {exp_tok} |")
            if r["skills_f1"] < 0.5:
                pred_s = ", ".join(sorted(r.get("predicted_skills", []))[:5])
                exp_s = ", ".join(sorted(r.get("expected_skills", []))[:5])
                lines.append(f"| {r['id']} | Kỹ năng (top 5) | {pred_s} | {exp_s} |")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="fake", help="fake | anthropic | openai | ollama")
    parser.add_argument("--model", default="", help="Model ID (unused for fake)")
    parser.add_argument("--prompt-version", default="1")
    parser.add_argument(
        "--data",
        default="synthetic",
        help="synthetic | dir:<path>",
    )
    args = parser.parse_args(argv)

    version = int(args.prompt_version)

    if args.provider == "fake":
        client = FakeLLM()
    else:
        import os
        os.environ.setdefault("LLM_PROVIDER", args.provider)
        if args.model:
            os.environ["LLM_MODEL"] = args.model
        client = get_llm_client()

    if args.data == "synthetic":
        labels, _jobs = _load_synthetic(SAMPLE_DIR)
        cv_dir = SAMPLE_DIR
        results = []
        for label in labels:
            cv_path = cv_dir / label.file_name
            if not cv_path.exists():
                results.append({"id": label.id, "ok": False, "error": "file missing"})
                continue
            results.append(_eval_cv_label(label, cv_path, client))
        data_source = "synthetic"
    elif args.data.startswith("dir:"):
        data_dir = Path(args.data[4:])
        entries = _load_dir(data_dir)
        results = []
        for entry in entries:
            path = entry["path"]
            try:
                data = path.read_bytes()
                mime = "application/pdf" if path.suffix == ".pdf" else (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                result = extract_text(data, mime)
                text, _, _ = redact_contacts(result.text)
                parsed = parse_cv(text, client=client, version=version)
                results.append({
                    "id": path.name,
                    "ok": True,
                    "name_match": 0,
                    "title_match": 0,
                    "location_match": 0,
                    "yoe_match": 0,
                    "skills_f1": 0.0,
                    "model": parsed.model,
                    "prompt_version": parsed.prompt_version,
                    "note": "no_ground_truth",
                })
            except Exception as exc:
                results.append({"id": path.name, "ok": False, "error": str(exc)})
        data_source = str(data_dir)
    else:
        sys.exit(f"--data phải là 'synthetic' hoặc 'dir:<đường dẫn>', không phải: {args.data!r}")

    agg = _aggregate(results)
    model_name = getattr(client, "model", "unknown")
    report = _write_report(
        results, agg, args.provider, model_name, str(version), data_source
    )

    print("=== Kết quả đánh giá Parse ===")
    for k, v in agg.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")
    print(f"\nBáo cáo: {report}")


if __name__ == "__main__":
    main()
