import argparse
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_engine
from app.services.integration_tokens import SERVICE_SCOPES, issue_token, revoke_token


def main() -> int:
    parser = argparse.ArgumentParser(description="Cấp hoặc thu hồi token dịch vụ tích hợp.")
    actions = parser.add_subparsers(dest="action", required=True)
    issue = actions.add_parser("issue")
    issue.add_argument("--sponsor", type=UUID, required=True)
    issue.add_argument("--scope", action="append", choices=SERVICE_SCOPES, required=True)
    issue.add_argument(
        "--expires-in-days", type=int, required=True, choices=range(1, 366), metavar="1..365"
    )
    revoke = actions.add_parser("revoke")
    revoke.add_argument("token_id", type=UUID)
    args = parser.parse_args()

    try:
        with Session(get_engine(get_settings().database_url)) as session:
            if args.action == "revoke":
                if not revoke_token(session, args.token_id):
                    print("Không tìm thấy token.", file=sys.stderr)
                    return 1
                session.commit()
                return 0
            token_id, raw = issue_token(
                session,
                args.sponsor,
                args.scope,
                datetime.now(UTC) + timedelta(days=args.expires_in_days),
            )
            session.commit()
    except (SQLAlchemyError, ValueError):
        print("Không thể thay đổi token. Kiểm tra tài khoản và migration.", file=sys.stderr)
        return 1
    print(f"Token ID: {token_id}", file=sys.stderr)
    print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
