"""Repeatable local M1 demo; all CV data comes through the real ingestion workflow."""

import json
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from io import TextIOWrapper
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, Settings, get_settings
from app.core.db import get_engine
from app.core.security import hash_password, verify_password
from app.models.applications import Application, StageEvent
from app.models.candidates import CvFile
from app.models.enums import ApplicationStage, HiringUnitKind, JobStatus, ProcessingStatus
from app.models.jobs import HiringUnit, Job, JobMember
from app.models.users import User, UserRole
from app.services.cv_files import upload_file
from app.services.embeddings import embed_job
from app.storage import build_storage
from app.workers.celery_app import celery_app
from app.workers.tasks import process_cv_file, score_application

SAMPLES = REPO_ROOT / "data/sample_cvs"
DEV_PASSWORD = "synthetic-dev-password"
DEV_USERS = (
    ("admin", UserRole.admin),
    ("lead", UserRole.lead),
    ("recruiter", UserRole.recruiter),
    ("recruiter2", UserRole.recruiter),
)
# These five unchanged files are reserved for the browser smoke test/manual upload.
SMOKE_IDS = frozenset({"cv_0008", "cv_0013", "cv_0019", "cv_0020", "cv_0029"})
UNIT_IDS = tuple(UUID(f"b73cc574-a24d-47df-8bbc-29bc883f100{i}") for i in range(3))
JOB_IDS = tuple(UUID(f"60de71d3-589a-43af-90da-40ec5a46100{i}") for i in range(5))


class SeedError(Exception):
    """Fixed, content-free CLI failure."""


def require_local_demo(settings: Settings) -> None:
    if (
        settings.app_env not in {"dev", "test"}
        or settings.llm_provider != "fake"
        or settings.embedding_provider != "fake"
        or settings.storage_backend != "local"
        or make_url(settings.database_url).host not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise SeedError("Seed chỉ dùng DB local, môi trường dev/test và hai provider fake.")


@contextmanager
def eager_workers():
    """Same Celery tasks and independent DB sessions, completed before CLI success."""
    previous = {key: celery_app.conf[key] for key in ("task_always_eager", "task_eager_propagates")}
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)
    try:
        yield
    finally:
        celery_app.conf.update(previous)


def seed_catalog(session: Session) -> tuple[dict[str, User], list[Job]]:
    """Also used by the disposable E2E server, without importing any sample CVs."""
    require_local_demo(get_settings())
    users = {}
    for login, role in DEV_USERS:
        email = f"dev-{login}@example.invalid"
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name=f"Tài khoản giả {login}",
                role=role,
                password_hash=hash_password(DEV_PASSWORD),
            )
            session.add(user)
            session.flush()
        elif (
            user.role != role
            or not user.is_active
            or not verify_password(DEV_PASSWORD, user.password_hash)
        ):
            raise SeedError("Tài khoản dev đã thay đổi; seed không ghi đè quyền hoặc mật khẩu.")
        users[login] = user
    units = []
    for index, unit_id in enumerate(UNIT_IDS):
        unit = session.get(HiringUnit, unit_id)
        if unit is None:
            unit = HiringUnit(
                id=unit_id,
                name=f"Đơn vị giả lập {index + 1}",
                kind=HiringUnitKind.department if index < 2 else HiringUnitKind.client,
            )
            session.add(unit)
        units.append(unit)
    session.flush()
    jobs = []
    source = json.loads((SAMPLES / "jobs.json").read_text(encoding="utf-8"))
    for index, item in enumerate(source["jobs"]):
        job = session.get(Job, JOB_IDS[index])
        if job is None:
            job = Job(
                id=JOB_IDS[index],
                hiring_unit_id=units[index % len(units)].id,
                owner_id=users["recruiter" if index % 2 == 0 else "recruiter2"].id,
                title=item["title"],
                description=item["description"],
                must_have=item["must_have"],
                nice_to_have=item["nice_to_have"],
                status=JobStatus.open,
                opened_at=datetime.now(UTC),
            )
            embed_job(job)
            session.add(job)
            session.flush()
        for login in ("recruiter", "recruiter2"):
            member_id = users[login].id
            membership = session.scalar(
                select(JobMember.id).where(
                    JobMember.job_id == job.id, JobMember.user_id == member_id
                )
            )
            if member_id != job.owner_id and membership is None:
                session.add(JobMember(job_id=job.id, user_id=member_id))
        jobs.append(job)
    session.commit()
    return users, jobs


def seed_demo(session: Session) -> dict[str, int]:
    settings = get_settings()
    require_local_demo(settings)
    storage = build_storage(settings)
    users, jobs = seed_catalog(session)
    # Labels select digital files only; parsing/scoring never reads expected outputs.
    files = []
    for path in sorted(SAMPLES.glob("cv_*.json")):
        label = json.loads(path.read_text(encoding="utf-8"))
        if (
            label["synthetic"] is True
            and label["layout"] != "scan"
            and label["id"] not in SMOKE_IDS
        ):
            files.append(SAMPLES / label["file_name"])
    if len(files) < 40:
        raise SeedError("Thiếu bộ CV giả kỹ thuật số; cần dữ liệu mẫu T06.")
    stages = (
        ApplicationStage.new,
        ApplicationStage.screening,
        ApplicationStage.submitted,
        ApplicationStage.interview,
        ApplicationStage.offer,
        ApplicationStage.hired,
    )
    with eager_workers():
        for index, path in enumerate(files[:40]):
            job = jobs[index % len(jobs)]
            result = upload_file(
                session,
                users["admin"],
                storage,
                data=path.read_bytes(),
                filename=path.name,
                job_id=job.id,
                index=index,
            )
            if result.cv_file is None:
                raise SeedError("Không thể tiếp nhận CV mẫu.")
            session.expire_all()
            cv = session.get_one(CvFile, result.cv_file.id)
            if cv.job_id != job.id or cv.uploaded_by != users["admin"].id:
                raise SeedError("CV mẫu đã thuộc dữ liệu khác; seed không thay đổi hồ sơ đó.")
            if cv.status != ProcessingStatus.done:
                # Resume an interrupted/failed seed through the same real worker.
                cv.status = ProcessingStatus.pending
                cv.error = None
                session.commit()
                process_cv_file.run(str(cv.id))
                session.refresh(cv)
            if cv.status != ProcessingStatus.done or cv.candidate_id is None:
                raise SeedError("Pipeline CV chưa hoàn tất; sửa môi trường rồi chạy lại seed.")
            application = session.scalar(
                select(Application).where(
                    Application.candidate_id == cv.candidate_id,
                    Application.job_id == job.id,
                    Application.deleted_at.is_(None),
                )
            )
            if application is None:
                raise SeedError("Thiếu hồ sơ ứng tuyển sau xử lý.")
            if application.ai_status != ProcessingStatus.done:
                application.ai_status = ProcessingStatus.pending
                session.commit()
                score_application.run(str(application.id))
                session.refresh(application)
            if application.ai_status != ProcessingStatus.done:
                raise SeedError("Chấm điểm chưa hoàn tất; sửa môi trường rồi chạy lại seed.")
            # Explicit synthetic history, never an AI decision or a real stage transition.
            if (
                session.scalar(
                    select(StageEvent.id).where(StageEvent.application_id == application.id)
                )
                is None
            ):
                application.stage = stages[(index // len(jobs)) % len(stages)]
                session.add(
                    StageEvent(
                        application_id=application.id,
                        from_stage=None,
                        to_stage=application.stage,
                        actor_id=users["admin"].id,
                        note="Lịch sử giả lập cho demo M1",
                    )
                )
                seed_recruitment(session, application)
            session.commit()
    return {"users": 4, "hiring_units": 3, "jobs": 5, "sample_cvs": 40}


def seed_recruitment(session: Session, application: Application) -> None:
    """Initial synthetic state only, alongside its initial event; never overwrite HR edits."""
    from datetime import date

    from app.models.recruitment import Interview, Offer, Placement

    if application.stage == ApplicationStage.interview:
        session.add(
            Interview(
                application_id=application.id,
                round=1,
                scheduled_at=datetime(2026, 11, 10, 2, tzinfo=UTC),
                duration_minutes=60,
                location_or_link="Phòng phỏng vấn giả lập",
                interviewers=["Người phỏng vấn giả lập"],
            )
        )
    if application.stage in {ApplicationStage.offer, ApplicationStage.hired}:
        session.add(
            Offer(
                application_id=application.id,
                salary=20000000,
                start_date=date(2026, 12, 1),
                status="accepted" if application.stage == ApplicationStage.hired else "sent",
                sent_at=datetime(2026, 11, 9, tzinfo=UTC),
                notes="Offer giả lập cho demo",
            )
        )
    if application.stage == ApplicationStage.hired:
        session.add(
            Placement(
                application_id=application.id,
                start_date=date(2026, 12, 1),
                guarantee_until=date(2027, 2, 1),
            )
        )


def main() -> int:
    try:
        settings = get_settings()
        require_local_demo(settings)
        with Session(get_engine(settings.database_url)) as session:
            counts = seed_demo(session)
    except SeedError as exc:
        print(str(exc))
        return 1
    except Exception:
        # DB/provider/file exceptions can contain CV content, credentials or paths.
        print("Seed thất bại. Kiểm tra DB, migration và dữ liệu mẫu rồi chạy lại.")
        return 1
    print(json.dumps({"status": "ok", **counts}))
    print("Tài khoản GIẢ chỉ dành cho dev (không dùng khi triển khai thật):")
    for login, _role in DEV_USERS:
        print(f"dev-{login}@example.invalid / {DEV_PASSWORD}")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
