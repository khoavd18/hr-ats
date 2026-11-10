"""Tests for T31: AI evaluation harness scripts.

All tests run offline (--provider fake --data synthetic).
No network, no real LLM, no PII in test data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent.parent  # repo root
SAMPLE_DIR = ROOT / "data" / "sample_cvs"

# Make eval/ importable
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_sample_data() -> bool:
    return (SAMPLE_DIR / "jobs.json").exists() and len(list(SAMPLE_DIR.glob("cv_*.json"))) > 0


pytestmark = pytest.mark.skipif(
    not _has_sample_data(),
    reason="data/sample_cvs/ not generated; run generate_synthetic_cvs.py first",
)


# ---------------------------------------------------------------------------
# run_parse_eval
# ---------------------------------------------------------------------------

class TestParseEval:
    def test_runs_offline_with_fake_and_synthetic(self, tmp_path):
        """Acceptance criterion: runs with --provider fake --data synthetic."""
        import eval.run_parse_eval as mod

        orig_reports = mod.REPORTS_DIR
        mod.REPORTS_DIR = tmp_path  # redirect output

        try:
            mod.main(["--provider", "fake", "--data", "synthetic"])
        finally:
            mod.REPORTS_DIR = orig_reports

    def test_generates_report_file(self, tmp_path):
        import eval.run_parse_eval as mod

        orig_reports = mod.REPORTS_DIR
        mod.REPORTS_DIR = tmp_path

        try:
            mod.main(["--provider", "fake", "--data", "synthetic"])
        finally:
            mod.REPORTS_DIR = orig_reports

        reports = list(tmp_path.glob("*-parse-*.md"))
        assert len(reports) == 1, "Should produce exactly one report"
        content = reports[0].read_text(encoding="utf-8")
        assert "# Báo cáo đánh giá Parse CV" in content
        assert "| Họ tên" in content

    def test_aggregate_has_all_metrics(self, tmp_path):
        import eval.run_parse_eval as mod

        # Load labels + run eval inline
        labels, _jobs = mod._load_synthetic(SAMPLE_DIR)
        client = mod.FakeLLM()
        results = []
        for label in labels[:5]:  # only first 5 for speed
            cv_path = SAMPLE_DIR / label.file_name
            results.append(mod._eval_cv_label(label, cv_path, client))
        agg = mod._aggregate(results)
        for key in ("n", "failed", "name_acc", "title_acc", "location_acc", "yoe_acc", "skills_f1"):
            assert key in agg, f"Missing key {key!r} in aggregate"

    def test_no_pii_in_report(self, tmp_path):

        import eval.run_parse_eval as mod
        from eval.schemas import CVLabel

        orig_reports = mod.REPORTS_DIR
        mod.REPORTS_DIR = tmp_path

        try:
            mod.main(["--provider", "fake", "--data", "synthetic"])
        finally:
            mod.REPORTS_DIR = orig_reports

        # Load all label emails/phones to ensure they don't appear in the report
        emails = set()
        phones = set()
        for p in SAMPLE_DIR.glob("cv_*.json"):
            lbl = CVLabel.model_validate_json(p.read_text(encoding="utf-8"))
            emails.add(lbl.email.lower())
            phones.add(lbl.phone.replace(" ", ""))

        for report in tmp_path.glob("*.md"):
            text = report.read_text(encoding="utf-8").lower()
            for email in emails:
                assert email not in text, f"PII email found in report: {email}"
            for phone in phones:
                assert phone not in text, f"PII phone found in report: {phone}"


# ---------------------------------------------------------------------------
# run_score_eval
# ---------------------------------------------------------------------------

class TestScoreEval:
    def test_runs_offline_with_fake_and_synthetic(self, tmp_path):
        """Acceptance criterion: runs with --provider fake --data synthetic."""
        import eval.run_score_eval as mod

        orig_reports = mod.REPORTS_DIR
        mod.REPORTS_DIR = tmp_path

        try:
            mod.main(["--provider", "fake", "--data", "synthetic"])
        finally:
            mod.REPORTS_DIR = orig_reports

    def test_generates_report_file(self, tmp_path):
        import eval.run_score_eval as mod

        orig_reports = mod.REPORTS_DIR
        mod.REPORTS_DIR = tmp_path

        try:
            mod.main(["--provider", "fake", "--data", "synthetic"])
        finally:
            mod.REPORTS_DIR = orig_reports

        reports = list(tmp_path.glob("*-score-*.md"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "# Báo cáo đánh giá chấm điểm CV" in content
        assert "precision@10" in content
        assert "kappa" in content.lower()

    def test_kappa_range(self):
        import eval.run_score_eval as mod

        y_true = ["high", "high", "medium", "low", "low"]
        y_pred = ["high", "medium", "medium", "low", "high"]
        kappa = mod._kappa(y_true, y_pred, mod.LEVEL_ORDER)
        assert -1.0 <= kappa <= 1.0

    def test_precision_at_k(self):
        import eval.run_score_eval as mod

        results = [
            {"ok": True, "ai_score": 90, "expected_level": "high"},
            {"ok": True, "ai_score": 80, "expected_level": "medium"},
            {"ok": True, "ai_score": 70, "expected_level": "low"},
            {"ok": True, "ai_score": 60, "expected_level": "high"},
            {"ok": False},  # error row: ignored
        ]
        p = mod._precision_at_k(results, k=3)
        # top 3 by score: 90(high), 80(medium), 70(low) → 2/3 positive
        assert abs(p - 2 / 3) < 0.01


# ---------------------------------------------------------------------------
# run_bias_check
# ---------------------------------------------------------------------------

class TestBiasCheck:
    def test_runs_offline_with_fake_and_synthetic(self, tmp_path):
        """Acceptance criterion: bias check reports score delta by name group."""
        import eval.run_bias_check as mod

        orig_reports = mod.REPORTS_DIR
        mod.REPORTS_DIR = tmp_path

        try:
            mod.main(["--provider", "fake", "--data", "synthetic"])
        finally:
            mod.REPORTS_DIR = orig_reports

    def test_generates_report_with_group_table(self, tmp_path):
        import eval.run_bias_check as mod

        orig_reports = mod.REPORTS_DIR
        mod.REPORTS_DIR = tmp_path

        try:
            mod.main(["--provider", "fake", "--data", "synthetic"])
        finally:
            mod.REPORTS_DIR = orig_reports

        reports = list(tmp_path.glob("*-bias-*.md"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "# Báo cáo kiểm tra thiên lệch" in content
        assert "Nam miền Bắc" in content  # group label present

    def test_no_names_in_report(self, tmp_path):
        """Bias report must not contain the fictional swap names (privacy)."""
        import eval.run_bias_check as mod

        orig_reports = mod.REPORTS_DIR
        mod.REPORTS_DIR = tmp_path

        try:
            mod.main(["--provider", "fake", "--data", "synthetic"])
        finally:
            mod.REPORTS_DIR = orig_reports

        for report in tmp_path.glob("*.md"):
            content = report.read_text(encoding="utf-8")
            # Actual fictional first names used as swap names should not appear
            for _, (_, names) in mod._NAMES.items():
                for name in names:
                    # We allow the group label (e.g. "Nam miền Bắc") but not the full swap name
                    assert name not in content, f"Swap name {name!r} found in bias report"

    def test_fake_scores_deterministic(self):
        """FakeLLM scores should be identical across two runs (deterministic)."""
        import eval.run_score_eval as mod

        labels, jobs = mod._load_synthetic(SAMPLE_DIR)
        label = labels[0]
        job = jobs.jobs[0]
        cv_path = SAMPLE_DIR / label.file_name

        client = mod.FakeLLM()
        rules = mod.ScoringRules()

        r1 = mod._eval_one(label, cv_path, job, client, rules)
        r2 = mod._eval_one(label, cv_path, job, client, rules)

        assert r1["ai_score"] == r2["ai_score"]
        assert r1["ai_level"] == r2["ai_level"]
