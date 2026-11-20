"""Synthetic PostgreSQL facts, real query/render/worker flow, in-memory SMTP."""

import json
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.errors import AppError
from app.models import Activity, EmailMessage, Job, User
from app.models.users import UserRole
from app.reports import queries, scheduled
from app.scripts import send_report
from app.workers import email, reports
from tests.api.test_reports import at
from tests.api.test_reports import dataset as dataset

SETTINGS = Settings(_env_file=None, frontend_origin="https://ats.example.invalid")
DAILY = at("11-01T18:00:00")
WEEKLY = at("11-09T08:30:00")


class Tables(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.cell = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self.tables[-1].append([])
        elif tag in {"td", "th"}:
            self.cell = ""

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.tables[-1][-1].append(self.cell)
            self.cell = None


@pytest.fixture
def managers(db_session, account):
    lead = User(
        email="t28-lead@example.invalid",
        full_name="Trưởng nhóm giả",
        password_hash=account.password_hash,
        role=UserRole.lead,
    )
    inactive = User(
        email="t28-inactive@example.invalid",
        full_name="Quản trị giả đã nghỉ",
        password_hash=account.password_hash,
        role=UserRole.admin,
        is_active=False,
    )
    db_session.add_all([lead, inactive])
    db_session.commit()
    return lead, inactive


@pytest.fixture
def runtime(db_session, monkeypatch):
    @contextmanager
    def session():
        yield db_session

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return DAILY.astimezone(tz or UTC)

    for module in (email, reports, send_report):
        monkeypatch.setattr(module, "worker_session", session)
        monkeypatch.setattr(module, "datetime", Clock)


@pytest.mark.parametrize(
    "kind,instant,start,end",
    [
        ("daily", "2026-11-01T16:59:59+00:00", "2026-11-01", "2026-11-02"),
        ("daily", "2026-11-01T17:00:00+00:00", "2026-11-02", "2026-11-03"),
        ("weekly", "2026-11-01T16:59:59+00:00", "2026-10-19", "2026-10-26"),
        ("weekly", "2026-11-01T17:00:00+00:00", "2026-10-26", "2026-11-02"),
        ("weekly", "2026-11-09T01:30:00+00:00", "2026-11-02", "2026-11-09"),
        ("weekly", "2027-01-04T01:30:00+00:00", "2026-12-28", "2027-01-04"),
        ("daily", "2028-02-29T11:00:00+00:00", "2028-02-29", "2028-03-01"),
    ],
)
def test_period_boundaries(kind, instant, start, end):
    params = scheduled.report_input(kind, datetime.fromisoformat(instant))
    assert params.from_date == date.fromisoformat(start)
    assert params.to_date == date.fromisoformat(end)


def test_report_rejects_naive_clock_and_unknown_kind():
    with pytest.raises(ValueError):
        scheduled.report_input("daily", datetime(2026, 11, 1))
    with pytest.raises(ValueError):
        scheduled.report_input("monthly", DAILY)


def test_daily_html_matches_queries_and_hand_computed_team(db_session, account, dataset):
    dataset.a.full_name = "Recruiter giả <script>không chạy</script>"
    db_session.commit()
    report = scheduled.build_report(db_session, account, "daily", DAILY, SETTINGS)
    tables = Tables(report.html).tables
    values = dict(tables[0][1:])
    assert {
        key: values[key]
        for key in ("CV mới", "Đã sàng lọc", "Đã gửi đơn vị tuyển", "Offer", "Nhận việc")
    } == {
        "CV mới": "2",
        "Đã sàng lọc": "2",
        "Đã gửi đơn vị tuyển": "1",
        "Offer": "1",
        "Nhận việc": "1",
    }
    assert values["Phí placement đã biết (VND)"] == "100"
    assert values["Tỉ lệ đồng thuận AI"] == "100,0%"
    start, end, filters, _ = queries.prepare(db_session, account, report.params, now=DAILY)
    assert values == dict(
        scheduled.metric_rows(queries.collect(db_session, start, end, filters)[None])
    )
    by_person = {row[0]: row[1:] for row in tables[1][1:]}
    assert by_person[dataset.a.full_name][:6] == ["1", "2", "0", "1", "1", "1"]
    assert by_person[dataset.b.full_name][:6] == ["1", "0", "1", "0", "0", "0"]
    assert "Bản nháp" in report.html and "https://ats.example.invalid/reports" in report.html
    assert "&lt;script&gt;" in report.html and "<script>" not in report.html
    assert "Ứng viên giả" not in report.html and dataset.a.email not in report.html
    assert "01/11/2026 18:00" in report.html and "Chưa có dữ liệu" in report.html


def test_weekly_comparison_and_top_jobs_share_kpi_population(db_session, account, dataset):
    dataset.j1.title = "Job giả <img src=x>"
    db_session.commit()
    report = scheduled.build_report(db_session, account, "weekly", WEEKLY, SETTINGS)
    tables = Tables(report.html).tables
    values = {row[0]: row[1:] for row in tables[0][1:]}
    assert values["CV mới"] == ["4", "3"]
    assert values["Đã sàng lọc"] == ["0", "3"]
    assert values["Đã gửi đơn vị tuyển"] == ["2", "1"]
    assert values["Nhận việc"] == ["3", "1"]
    assert values["Phí placement đã biết (VND)"] == ["300", "100"]
    assert values["Tỉ lệ đồng thuận AI"] == ["60,0%", "50,0%"]
    assert tables[-1] == [["Job", "Hạn tuyển"], [dataset.j1.title, "01/11/2026"]]
    assert "26/10/2026 – 01/11/2026" in report.html
    assert "&lt;img src=x&gt;" in report.html and "<img" not in report.html
    assert "Chưa gán / hệ thống" in report.html
    assert "Job trễ hạn hiện tại: 1" in report.html


def test_top_overdue_is_limited_sorted_and_excludes_closed_or_full(db_session, account, dataset):
    for day in range(1, 9):
        db_session.add(
            Job(
                title=f"Job giả {day}",
                description="",
                owner_id=dataset.a.id,
                hiring_unit_id=dataset.u1.id,
                status="open",
                deadline=date(2026, 10, day),
                headcount=1,
            )
        )
    db_session.add(
        Job(
            title="Job giả đóng",
            description="",
            owner_id=dataset.a.id,
            hiring_unit_id=dataset.u1.id,
            status="closed",
            deadline=date(2026, 1, 1),
            headcount=1,
        )
    )
    db_session.commit()
    filters = queries.Filters(account, WEEKLY)
    assert queries.top_overdue_jobs(db_session, filters) == [
        (f"Job giả {day}", f"0{day}/10/2026") for day in range(1, 6)
    ]
    assert queries.overdue_jobs(db_session, DAILY, WEEKLY, filters)[None] == 9


@pytest.mark.parametrize("kind", ["daily", "weekly"])
def test_empty_report_preserves_zero_null_and_draft(db_session, account, kind):
    report = scheduled.build_report(db_session, account, kind, DAILY, SETTINGS)
    values = {row[0]: row[1:] for row in Tables(report.html).tables[0][1:]}
    assert set(values["CV mới"]) == {"0"}
    assert set(values["Phí placement đã biết (VND)"]) == {"Chưa có dữ liệu"}
    assert set(values["Tỉ lệ đồng thuận AI"]) == {"Chưa có dữ liệu"}
    assert "Bản nháp" in report.html


@pytest.mark.parametrize("kind", ["daily", "weekly"])
def test_producers_send_only_active_managers_and_deduplicate(
    db_session,
    account,
    dataset,
    managers,
    runtime,
    email_outbox,
    kind,
):
    task = reports.generate_daily_report if kind == "daily" else reports.generate_weekly_report
    task.run()
    assert {str(m["To"]) for m in email_outbox} == {account.email, managers[0].email}
    assert len(email_outbox) == 2
    rows = db_session.scalars(select(EmailMessage)).all()
    assert len(rows) == 2 and all(row.status == "sent" for row in rows)
    assert all(scheduled.report_kind(row) == kind for row in rows)
    assert all(m.get_body(preferencelist=("html",)) is not None for m in email_outbox)
    assert "CV mới\t" in email_outbox[0].get_body(preferencelist=("plain",)).get_content()
    task.run()
    assert len(email_outbox) == 2
    activities = db_session.scalars(select(Activity).where(Activity.occurred_at > DAILY)).all()
    assert len(activities) == 2
    assert all(
        row.actor_id is None and set(row.payload) == {"email_message_id"} for row in activities
    )


@pytest.mark.parametrize("change", ["role", "inactive", "recipient", "marker", "id"])
def test_worker_rechecks_permission_and_marker(
    db_session,
    account,
    runtime,
    email_outbox,
    change,
):
    args = scheduled.queue_reports(db_session, "daily", DAILY, SETTINGS)[0]
    row = db_session.get(EmailMessage, UUID(args[0]))
    if change == "role":
        account.role = UserRole.recruiter
    elif change == "inactive":
        account.is_active = False
    elif change == "recipient":
        account.email = "changed-t28@example.invalid"
    elif change == "marker":
        row.message_id = "<untrusted@hr-ats.invalid>"
    else:
        row.id = uuid4()
    db_session.commit()
    email.send_email_message.run(str(row.id), row.message_id, row.scheduled_for.isoformat())
    assert email_outbox == [] and row.status == "failed"


def test_recruiter_cannot_build_team_report(db_session, account):
    account.role = UserRole.recruiter
    db_session.commit()
    with pytest.raises(AppError, match="Không có quyền"):
        scheduled.build_report(db_session, account, "daily", DAILY, SETTINGS)
    assert scheduled.queue_reports(db_session, "daily", DAILY, SETTINGS) == []


def test_publish_failure_recovered_without_duplicate_rows(
    db_session,
    account,
    runtime,
    email_outbox,
    monkeypatch,
):
    original = email.send_email_message.apply_async

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic broker failure")

    monkeypatch.setattr(email.send_email_message, "apply_async", fail)
    assert reports.generate_report("daily") == 0
    row = db_session.scalar(select(EmailMessage))
    assert row.status == "queued"
    checkpoint = (row.id, row.message_id, row.body_html, row.scheduled_for)
    monkeypatch.setattr(email.send_email_message, "apply_async", original)
    assert reports.generate_report("daily") == 1
    assert len(email_outbox) == 1 and row.status == "sent"
    assert (row.id, row.message_id, row.body_html) == checkpoint[:3]


def test_retry_crossing_midnight_keeps_snapshot_and_checkpoint(
    db_session,
    account,
    runtime,
    email_outbox,
    monkeypatch,
):
    args = scheduled.queue_reports(db_session, "weekly", DAILY, SETTINGS)[0]
    row = db_session.get(EmailMessage, UUID(args[0]))
    original_html, original_deliver = row.body_html, email.deliver

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic secret SMTP error")

    monkeypatch.setattr(email, "deliver", fail)
    assert email.send_email_message.apply(args=list(args)).successful()
    assert row.status == "failed" and row.scheduled_for == DAILY + timedelta(seconds=60)
    assert "synthetic" not in row.error and "secret" not in row.error

    class NextDay(datetime):
        @classmethod
        def now(cls, tz=None):
            return (DAILY + timedelta(days=1)).astimezone(tz or UTC)

    monkeypatch.setattr(email, "datetime", NextDay)
    monkeypatch.setattr(email, "deliver", original_deliver)
    email.send_email_message.run(*args)  # Old checkpoint cannot send.
    assert email_outbox == []
    email.send_email_message.run(str(row.id), row.message_id, row.scheduled_for.isoformat(), 1)
    assert len(email_outbox) == 1 and row.status == "sent"
    assert email_outbox[0].get_body(preferencelist=("html",)).get_content().strip() == original_html


def test_reports_share_the_global_smtp_limit(
    db_session, account, runtime, email_outbox, monkeypatch
):
    args = scheduled.queue_reports(db_session, "daily", DAILY, SETTINGS)[0]
    db_session.add(
        EmailMessage(
            created_by=account.id,
            to_email="synthetic@example.invalid",
            subject="Thư giả",
            body_html="<p>Thư giả</p>",
            status="sent",
            sent_at=DAILY - timedelta(minutes=10),
        )
    )
    db_session.commit()
    monkeypatch.setattr(
        email, "get_settings", lambda: Settings(_env_file=None, email_rate_limit_per_hour=1)
    )
    email.send_email_message.apply(args=list(args))
    row = db_session.get(EmailMessage, UUID(args[0]))
    assert email_outbox == [] and row.status == "queued" and row.scheduled_for > DAILY


@pytest.mark.parametrize("kind", ["daily", "weekly"])
def test_cli_dry_run_writes_utf8_without_queue_or_mail(
    db_session,
    account,
    dataset,
    runtime,
    email_outbox,
    tmp_path,
    capsys,
    monkeypatch,
    kind,
):
    def unexpected(*args, **kwargs):
        pytest.fail("Dry run must never publish")

    monkeypatch.setattr(send_report, "generate_report", unexpected)
    target = tmp_path / "preview.html"
    before = db_session.scalar(select(func.count()).select_from(Activity))
    assert send_report.main([f"--{kind}", "--dry-run", "--output", str(target)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert "Báo cáo tuyển dụng" in target.read_text(encoding="utf-8")
    assert email_outbox == []
    assert db_session.scalar(select(func.count()).select_from(EmailMessage)) == 0
    assert db_session.scalar(select(func.count()).select_from(Activity)) == before
    assert send_report.main([f"--{kind}", "--dry-run", "--output", str(target)]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "REPORT_FAILED"


def test_cli_missing_manager_and_errors_do_not_leak(
    db_session, runtime, tmp_path, capsys, monkeypatch
):
    target = tmp_path / "preview.html"
    assert send_report.main(["--daily", "--dry-run", "--output", str(target)]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "NO_REPORT_RECIPIENTS"
    assert not target.exists()

    @contextmanager
    def broken():
        raise RuntimeError("synthetic private connection details")
        yield

    monkeypatch.setattr(send_report, "worker_session", broken)
    assert send_report.main(["--weekly", "--dry-run"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "error", "code": "REPORT_FAILED"}


@pytest.mark.parametrize("args", [[], ["--daily", "--weekly"], ["--daily", "--output", "x.html"]])
def test_cli_requires_one_kind_and_dry_run_for_output(args):
    with pytest.raises(SystemExit) as error:
        send_report.main(args)
    assert error.value.code == 2


def test_concurrent_producers_commit_before_publish_and_real_cli(
    empty_engine,
    tmp_path,
    monkeypatch,
    email_outbox,
):
    import os
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from alembic import command
    from sqlalchemy.orm import Session

    from tests.conftest import migration_config

    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(empty_engine) as session:
        for role in UserRole:
            session.add(
                User(
                    email=f"t28-{role.value}@example.invalid",
                    full_name=f"Người giả {role.value}",
                    role=role,
                    password_hash="unused-synthetic-hash",
                )
            )
        session.commit()
    barrier = Barrier(2)
    now = datetime.now(UTC)

    def run():
        with Session(empty_engine) as session:
            barrier.wait(timeout=10)
            return scheduled.queue_reports(session, "daily", now, SETTINGS)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert len(results[0]) == 2 and results[0] == results[1]

    @contextmanager
    def worker_session():
        with Session(empty_engine) as session:
            yield session

    monkeypatch.setattr(reports, "worker_session", worker_session)
    published = []

    def observe(*, args):
        with Session(empty_engine) as session:
            assert session.scalar(select(func.count()).select_from(EmailMessage)) == 2
            row = session.get(EmailMessage, UUID(args[0]))
            assert row.status == "queued"
            assert args == [str(row.id), row.message_id, row.scheduled_for.isoformat()]
            assert row.to_email not in str(args) and row.subject not in str(args)
            published.append(args)

    monkeypatch.setattr(email.send_email_message, "apply_async", observe)
    assert reports.generate_report("daily") == len(published) == 2

    # Separate CLI processes, the exact documented commands, isolated database.
    # This is always --dry-run; no worker/SMTP/remote provider is started.
    env = dict(os.environ, DATABASE_URL=empty_engine.url.render_as_string(hide_password=False))
    for kind in ("daily", "weekly"):
        target = tmp_path / f"real-{kind}.html"
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "app.scripts.send_report",
                f"--{kind}",
                "--dry-run",
                "--output",
                str(target),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["status"] == "ok"
        assert "Báo cáo tuyển dụng" in target.read_text(encoding="utf-8")
    assert email_outbox == []
    with Session(empty_engine) as session:
        assert session.scalar(select(func.count()).select_from(EmailMessage)) == 2
        assert session.scalar(select(func.count()).select_from(Activity)) == 0
