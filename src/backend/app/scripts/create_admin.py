import argparse
from getpass import getpass

from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import AppError
from app.models.users import UserRole
from app.schemas.users import UserCreate
from app.services.users import create_user


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo tài khoản quản trị.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default="Quản trị viên")
    args = parser.parse_args()
    try:
        password = getpass("Mật khẩu (12–128 ký tự): ")
        if password != getpass("Nhập lại mật khẩu: "):
            print("Mật khẩu nhập lại không khớp.")
            return 1
        data = UserCreate(
            email=args.email,
            full_name=args.full_name,
            role=UserRole.admin,
            password=SecretStr(password),
        )
        with Session(get_engine(get_settings().database_url)) as session:
            create_user(session, None, data)
    except ValidationError:
        print("Email, tên hoặc mật khẩu chưa hợp lệ.")
        return 1
    except AppError as exc:
        print(exc.message)
        return 1
    except SQLAlchemyError:
        print("Không thể tạo tài khoản. Kiểm tra kết nối và chạy migration trước.")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Đã huỷ tạo tài khoản.")
        return 1
    print("Đã tạo tài khoản quản trị.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
