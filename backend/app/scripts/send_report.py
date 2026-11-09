"""Preview reports offline from SMTP, or enqueue the same fixed production flow."""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from io import TextIOWrapper
from pathlib import Path
from uuid import uuid4

from app.core.config import REPO_ROOT, get_settings
from app.reports.scheduled import ReportKind, build_report, recipients
from app.workers.reports import generate_report
from app.workers.tasks import worker_session


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gửi hoặc xem trước báo cáo tuyển dụng.")
    kind = parser.add_mutually_exclusive_group(required=True)
    kind.add_argument("--daily", action="store_true", help="Báo cáo ngày hiện tại")
    kind.add_argument("--weekly", action="store_true", help="Báo cáo tuần trước")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ tạo tệp HTML, không gửi")
    parser.add_argument("--output", type=Path, help="Đường dẫn tệp HTML mới khi xem trước")
    args = parser.parse_args(argv)
    if args.output is not None and not args.dry_run:
        parser.error("--output cần --dry-run")
    report_kind: ReportKind = "daily" if args.daily else "weekly"
    try:
        if args.dry_run:
            now = datetime.now(UTC)
            with worker_session() as session:
                actors = recipients(session)
                if not actors:
                    print('{"status": "error", "code": "NO_REPORT_RECIPIENTS"}')
                    return 1
                report = build_report(session, actors[0], report_kind, now, get_settings())
            path = args.output or (
                REPO_ROOT
                / "var"
                / "reports"
                / f"bao-cao-{report_kind}-{report.params.from_date}-{uuid4().hex[:8]}.html"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            # Never overwrite an unrelated file supplied with --output.
            with path.open("x", encoding="utf-8") as output:
                output.write(report.html)
            print(json.dumps({"status": "ok", "file": str(path.resolve())}))
        else:
            published = generate_report(report_kind)
            print(json.dumps({"status": "ok", "published": published}))
    except Exception:
        print('{"status": "error", "code": "REPORT_FAILED"}')
        return 1
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
