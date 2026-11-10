"""Download public CV evaluation datasets.

Usage:
    python scripts/download_datasets.py [--out var/datasets]

Datasets requiring terms agreement (Viet-Resume-VQA, CareerCorpus) print
instructions instead of downloading automatically. Kaggle downloads require
~/.kaggle/kaggle.json (API token from kaggle.com/account).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _require_kaggle() -> bool:
    """Return True if kaggle credentials exist."""
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if kaggle_json.exists():
        return True
    print(
        "⚠  Kaggle API token không tìm thấy tại ~/.kaggle/kaggle.json\n"
        "   Truy cập https://www.kaggle.com/account → API → Create New Token\n"
        "   Lưu file vào ~/.kaggle/kaggle.json rồi chạy lại.",
        file=sys.stderr,
    )
    return False


def _download_kaggle(dataset: str, out: Path) -> None:
    """Download a Kaggle dataset into out/."""
    try:
        import kaggle  # type: ignore[import-untyped]
    except ImportError:
        print("   pip install kaggle", file=sys.stderr)
        return
    out.mkdir(parents=True, exist_ok=True)
    kaggle.api.authenticate()
    kaggle.api.dataset_download_files(dataset, path=str(out), unzip=True)
    print(f"   ✓ Đã tải {dataset} → {out}")


def _download_hf(repo_id: str, out: Path, config: str | None = None) -> None:
    """Download a Hugging Face dataset into out/."""
    try:
        from datasets import load_dataset  # type: ignore[import-untyped]
    except ImportError:
        print("   pip install datasets", file=sys.stderr)
        return
    out.mkdir(parents=True, exist_ok=True)
    kwargs: dict = {"path": repo_id, "cache_dir": str(out)}
    if config:
        kwargs["name"] = config
    ds = load_dataset(**kwargs)
    print(f"   ✓ Đã tải {repo_id} → {out}: {ds}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "var" / "datasets"))
    args = parser.parse_args(argv)
    base = Path(args.out)

    print("=== Download bộ dữ liệu CV công khai ===\n")

    # --- Kaggle datasets ---
    if _require_kaggle():
        print("1. Resume Dataset (Kaggle snehaanbhawal/resume-dataset)")
        _download_kaggle("snehaanbhawal/resume-dataset", base / "resume-dataset")

        print("2. UpdatedResumeDataSet (Kaggle gauravduttakiit/resume-dataset)")
        _download_kaggle("gauravduttakiit/resume-dataset", base / "updated-resume-dataset")
    else:
        print("1–2. Bỏ qua Kaggle datasets (thiếu token).\n")

    # --- Hugging Face datasets (auto download) ---
    print("\n3. resume-job-description-fit (Hugging Face)")
    _download_hf(
        "cnamuangtoun/resume-job-description-fit",
        base / "resume-jd-fit",
    )

    print("\n4. ResumeAtlas (Hugging Face) — giấy phép CC BY-NC-ND, chỉ phi thương mại")
    _download_hf("ahmedheakl/resume-atlas", base / "resume-atlas")

    # --- Datasets requiring manual agreement ---
    print(
        "\n5. CareerCorpus (Mendeley Data wzzwn37gmd)\n"
        "   Yêu cầu đăng nhập và đồng ý điều khoản tại:\n"
        "   https://data.mendeley.com/datasets/wzzwn37gmd\n"
        "   Sau khi tải, giải nén vào: " + str(base / "careercorpus")
    )

    print(
        "\n6. Viet-Resume-VQA (Hugging Face 5CD-AI/Viet-Resume-VQA)\n"
        "   Yêu cầu đồng ý điều khoản tại Hugging Face trước khi tải:\n"
        "   https://huggingface.co/datasets/5CD-AI/Viet-Resume-VQA\n"
        "   Sau đó chạy: huggingface-cli login\n"
        "   Rồi chạy lại script này, hoặc tải thủ công vào: "
        + str(base / "viet-resume-vqa")
    )

    print(
        "\n7. VietJobs (GitHub VinNLP/VietJobs)\n"
        "   git clone https://github.com/VinNLP/VietJobs "
        + str(base / "vietjobs")
    )

    print("\nXong! Dữ liệu tải về nằm trong:", base)


if __name__ == "__main__":
    main()
