import json
import os
import subprocess
import sys

import pytest

from app.ai.embed import EmbeddingError
from app.scripts import reembed


def test_help_works_even_with_windows_legacy_stdout_encoding():
    result = subprocess.run(
        [sys.executable, "-m", "app.scripts.reembed", "--help"],
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True,
        encoding="utf-8",
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "--all" in result.stdout and "ẩn danh" in result.stdout


def test_cli_requires_explicit_all():
    with pytest.raises(SystemExit) as caught:
        reembed.main([])
    assert caught.value.code == 2


def test_cli_app_error_has_only_safe_code(monkeypatch, capsys):
    def fail(*args):
        raise EmbeddingError()

    monkeypatch.setattr(reembed, "reembed_session", fail)
    assert reembed.main(["--all"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "error", "code": "EMBEDDING_FAILED"}


def test_cli_invalid_config_is_safe(monkeypatch, capsys):
    monkeypatch.setenv("EMBEDDING_DIM", "private-sentinel")
    assert reembed.main(["--all"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "error", "code": "INVALID_SETTINGS"}
