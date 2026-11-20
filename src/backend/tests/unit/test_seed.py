import pytest

from app.core.config import Settings
from app.scripts import seed


@pytest.mark.parametrize(
    "update",
    [
        {"app_env": "prod"},
        {"llm_provider": "anthropic"},
        {"embedding_provider": "local"},
        {"storage_backend": "s3"},
        {"database_url": "postgresql+psycopg://hr:hr@remote.invalid/hr_ats"},
    ],
)
def test_seed_refuses_nonlocal_or_real_providers_before_opening_db(monkeypatch, capsys, update):
    settings = Settings(_env_file=None).model_copy(update=update)
    monkeypatch.setattr(seed, "get_settings", lambda: settings)

    def unexpected(*args):
        pytest.fail("Unsafe seed must never open a DB connection")

    monkeypatch.setattr(seed, "get_engine", unexpected)
    assert seed.main() == 1
    assert "Seed chỉ dùng DB local" in capsys.readouterr().out


def test_cli_failure_does_not_disclose_exception_content(monkeypatch, capsys):
    def fail(*args):
        raise RuntimeError("SYNTHETIC_PRIVATE_SENTINEL")

    monkeypatch.setattr(seed, "get_engine", fail)
    assert seed.main() == 1
    output = capsys.readouterr()
    assert "SYNTHETIC_PRIVATE_SENTINEL" not in output.out + output.err
    assert "Seed thất bại" in output.out


def test_eager_configuration_restored_after_failure():
    previous = seed.celery_app.conf.task_always_eager
    with pytest.raises(RuntimeError), seed.eager_workers():
        assert seed.celery_app.conf.task_always_eager is True
        raise RuntimeError("synthetic")
    assert seed.celery_app.conf.task_always_eager == previous
