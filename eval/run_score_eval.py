"""Evaluate CV scoring accuracy against ground-truth labels.

Metrics:
  - precision@10: fraction of top-10 scored CVs labelled high/medium
  - Cohen's kappa: agreement between ai_level and label
  - Per-level confusion matrix

Usage:
    # Offline (no network, synthetic data only)
    uv run python eval/run_score_eval.py --provider fake --data synthetic

    # With JD-fit public dataset
    uv run python eval/run_score_eval.py --provider fake \\
        --data dir:var/datasets/resume-jd-fit

    # Set custom data dir via env (CV without public labels use --data dir:)
    EVAL_DATA_DIR=path/to/anon_cvs uv run python eval/run_score_eval.py --provider fake
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.anonymize import anonymize  # noqa: E402
from app.ai.extract import ExtractionError, extract_text  # noqa: E402
from app.ai.llm import FakeLLM, get_llm_client  # noqa: E402
from app.ai.redact import redact_contacts  # noqa: E402
from app.ai.score import score_cv  # noqa: E402
from app.ai.scoring_rules import ScoringRules, compute_score  # noqa: E402

from eval.schemas import CVLabel, JobDataset  # noqa: E402

SAMPLE_DIR = ROOT / "data" / "sample_cvs"
REPORTS_DIR = ROOT / "eval" / "reports"

LEVEL_ORDER = ["high", "medium", "low", "insufficient"]
# Which levels count as "good" for precision@k
POSITIVE_LEVELS = {"high", "medium"}


# ---------------------------------------------------------------------------
# Cohen's kappa
# ---------------------------------------------------------------------------

def _kappa(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    """Unweighted Cohen's kappa for multi-class labels."""
    n = len(y_true)
    if n == 0:
        return 0.0
    idx = {lbl: i for i, lbl in enumerate(labels)}
    k = len(labels)
    conf = [[0] * k for _ in range(k)]
    for yt, yp in zip(y_true, y_pred, strict=True):
        if yt in idx and yp in idx:
            conf[idx[yt]][idx[yp]] += 1
    obs_agree = sum(conf[i][i] for i in range(k)) / n
    p_true = [sum(conf[i]) / n for i in range(k)]
    p_pred = [sum(conf[row][i] for row in range(k)) / n for i in range(k)]
    expected = sum(p_true[i] * p_pred[i] for i in range(k))
    if expected >= 1.0:
        return 1.0
    return (obs_agree - expected) / (1.0 - expected)


# ---------------------------------------------------------------------------
# Data loader
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


# ---------------------------------------------------------------------------
# Core evaluation (one CV × one Job)
# ---------------------------------------------------------------------------

def _eval_one(
    label: CVLabel,
    cv_path: Path,
    job: Any,
    client: Any,
    rules: ScoringRules,
) -> dict:
    try:
        data = cv_path.read_bytes()
        mime = "application/pdf" if cv_path.suffix == ".pdf" else (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        extract_result = extract_text(data, mime)
        redacted, _, _ = redact_contacts(extract_result.text)
        anon_text = anonymize(redacted, label.full_name)
        score_result = score_cv(
            anon_text,
            job_title=job.title,
            job_description=job.description,
            must_have=job.must_have,
            nice_to_have=job.nice_to_have,
            client=client,
        )
        computed = compute_score(score_result.judged.criteria, anon_text, rules=rules)
        expected = label.expected_level.get(job.id, "insufficient")
        return {
            "id": label.id,
            "job_id": job.id,
            "ok": True,
            "ai_level": computed.level.value,
            "ai_score": computed.score,
            "expected_level": expected,
            "model": score_result.model,
            "prompt_version": score_result.prompt_version,
        }
    except (ExtractionError, Exception) as exc:
        return {
            "id": label.id,
            "job_id": job.id if hasattr(job, "id") else "?",
            "ok": False,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Precision@k
# ---------------------------------------------------------------------------

def _precision_at_k(results: list[dict], k: int = 10) -> float:
    ok = [r for r in results if r.get("ok")]
    ranked = sorted(ok, key=lambda r: r.get("ai_score", 0), reverse=True)
    top_k = ranked[:k]
    if not top_k:
        return 0.0
    return sum(1 for r in top_k if r["expected_level"] in POSITIVE_LEVELS) / len(top_k)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _write_report(
    results: list[dict],
    provider: str,
    model: str,
    prompt_version: str,
    data_source: str,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = model.replace("/", "-").replace(":", "-")
    path = REPORTS_DIR / f"{today}-score-{slug}-v{prompt_version}.md"

    ok = [r for r in results if r.get("ok")]
    errors = [r for r in results if not r.get("ok")]

    # Per-job breakdown
    per_job: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        per_job[r["job_id"]].append(r)

    lines = [
        "# Báo cáo đánh giá chấm điểm CV",
        "",
        "| Thông số | Giá trị |",
        "|---|---|",
        f"| Ngày | {today} |",
        f"| Provider | {provider} |",
        f"| Model | {model} |",
        f"| Prompt version | v{prompt_version} |",
        f"| Nguồn dữ liệu | {data_source} |",
        f"| Tổng mẫu (ok) | {len(ok)} |",
        f"| Lỗi | {len(errors)} |",
        "",
        "## Chỉ số tổng hợp",
        "",
    ]

    if ok:
        all_true = [r["expected_level"] for r in ok]
        all_pred = [r["ai_level"] for r in ok]
        kappa = _kappa(all_true, all_pred, LEVEL_ORDER)
        p10 = _precision_at_k(ok, 10)
        lines += [
            "| Chỉ số | Giá trị |",
            "|---|---|",
            f"| precision@10 | {p10:.1%} |",
            f"| Cohen's kappa | {kappa:.3f} |",
            "",
            "## Ma trận nhầm lẫn (tất cả Job)",
            "",
            "| Nhãn \\ Dự đoán | " + " | ".join(LEVEL_ORDER) + " |",
            "|---|" + "---|" * len(LEVEL_ORDER),
        ]
        idx = {lbl: i for i, lbl in enumerate(LEVEL_ORDER)}
        conf = [[0] * len(LEVEL_ORDER) for _ in LEVEL_ORDER]
        for yt, yp in zip(all_true, all_pred, strict=True):
            if yt in idx and yp in idx:
                conf[idx[yt]][idx[yp]] += 1
        for i, lbl in enumerate(LEVEL_ORDER):
            lines.append("| " + lbl + " | " + " | ".join(str(c) for c in conf[i]) + " |")
        lines.append("")

        lines.append("## Kết quả theo Job\n")
        for job_id, job_results in sorted(per_job.items()):
            jt = [r["expected_level"] for r in job_results]
            jp = [r["ai_level"] for r in job_results]
            jk = _kappa(jt, jp, LEVEL_ORDER)
            jp10 = _precision_at_k(job_results, min(10, len(job_results)))
            lines.append(
                f"**{job_id}**: {len(job_results)} CV, "
                f"precision@{min(10,len(job_results))}={jp10:.1%}, kappa={jk:.3f}"
            )
        lines.append("")

    # 10 worst examples (expected≠predicted, anonymised)
    wrong = [r for r in ok if r["ai_level"] != r["expected_level"]][:10]
    if wrong:
        lines += [
            "## 10 ví dụ sai tiêu biểu (đã ẩn danh)",
            "",
            "| ID | Job | Dự đoán | Nhãn thật | Điểm |",
            "|---|---|---|---|---|",
        ]
        for r in wrong:
            lines.append(
                f"| {r['id']} | {r['job_id']} | {r['ai_level']} "
                f"| {r['expected_level']} | {r.get('ai_score', '?')} |"
            )
        lines.append("")

    if errors:
        lines += ["## Lỗi", "", "| ID | Job | Lỗi |", "|---|---|---|"]
        for r in errors:
            lines.append(f"| {r['id']} | {r.get('job_id','?')} | {r.get('error','')} |")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="fake")
    parser.add_argument("--model", default="")
    parser.add_argument("--prompt-version", default="1")
    parser.add_argument("--data", default="synthetic")
    args = parser.parse_args(argv)

    version = int(args.prompt_version)
    rules = ScoringRules()

    if args.provider == "fake":
        client = FakeLLM()
    else:
        import os
        os.environ.setdefault("LLM_PROVIDER", args.provider)
        if args.model:
            os.environ["LLM_MODEL"] = args.model
        client = get_llm_client()

    if args.data == "synthetic":
        labels, jobs_ds = _load_synthetic(SAMPLE_DIR)
        results = []
        for label in labels:
            cv_path = SAMPLE_DIR / label.file_name
            if not cv_path.exists():
                for job in jobs_ds.jobs:
                    results.append(
                        {"id": label.id, "job_id": job.id, "ok": False, "error": "file missing"}
                    )
                continue
            for job in jobs_ds.jobs:
                results.append(_eval_one(label, cv_path, job, client, rules))
        data_source = "synthetic"
    elif args.data.startswith("dir:"):
        data_dir = Path(args.data[4:])
        # Try to load synthetic jobs for scoring
        jobs_path = SAMPLE_DIR / "jobs.json"
        if not jobs_path.exists():
            sys.exit(f"Cần file jobs.json tại {jobs_path}")
        jobs_ds = JobDataset.model_validate_json(jobs_path.read_text(encoding="utf-8"))
        files = sorted(
            p
            for ext in ("*.pdf", "*.docx")
            for p in data_dir.glob(ext)
        )
        if not files:
            sys.exit(f"Không tìm thấy PDF/DOCX trong {data_dir}")
        # Create dummy labels (no ground truth)
        results = []
        for path in files:
            for job in jobs_ds.jobs:
                try:
                    data = path.read_bytes()
                    mime = "application/pdf" if path.suffix == ".pdf" else (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    extract_result = extract_text(data, mime)
                    redacted, _, _ = redact_contacts(extract_result.text)
                    anon_text = anonymize(redacted, "")
                    score_result = score_cv(
                        anon_text,
                        job_title=job.title,
                        job_description=job.description,
                        must_have=job.must_have,
                        nice_to_have=job.nice_to_have,
                        client=client,
                    )
                    computed = compute_score(score_result.judged.criteria, anon_text, rules=rules)
                    results.append({
                        "id": path.name,
                        "job_id": job.id,
                        "ok": True,
                        "ai_level": computed.level.value,
                        "ai_score": computed.score,
                        "expected_level": "unknown",
                        "model": score_result.model,
                        "prompt_version": score_result.prompt_version,
                        "note": "no_ground_truth",
                    })
                except Exception as exc:
                    results.append(
                        {"id": path.name, "job_id": job.id, "ok": False, "error": str(exc)}
                    )
        data_source = str(data_dir)
    else:
        sys.exit("--data phải là 'synthetic' hoặc 'dir:<đường dẫn>'")

    model_name = getattr(client, "model", "unknown")
    report = _write_report(results, args.provider, model_name, str(version), data_source)

    ok = [r for r in results if r.get("ok")]
    print("=== Kết quả đánh giá chấm điểm ===")
    print(f"  Tổng mẫu: {len(results)}, ok: {len(ok)}, lỗi: {len(results) - len(ok)}")
    if ok and all(r.get("expected_level", "unknown") != "unknown" for r in ok):
        all_true = [r["expected_level"] for r in ok]
        all_pred = [r["ai_level"] for r in ok]
        print(f"  precision@10: {_precision_at_k(ok, 10):.1%}")
        print(f"  Cohen's kappa: {_kappa(all_true, all_pred, LEVEL_ORDER):.3f}")
    print(f"\nBáo cáo: {report}")


if __name__ == "__main__":
    main()
