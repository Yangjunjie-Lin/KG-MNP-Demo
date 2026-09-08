"""Orchestration unit failures plus real owned API/Worker lifecycle smoke."""
import io
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools.run_browser_verification import ROOT, read_ready, wait_healthy


def test_silent_child_cannot_block_readiness_forever():
    process = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.readline()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        with pytest.raises(TimeoutError):
            read_ready(process, .05)
    finally:
        process.stdin.write("STOP\n")
        process.stdin.flush()
        assert process.wait(timeout=10) == 0
        process.stdin.close()
        process.stdout.close()


@pytest.mark.parametrize("line", ["", "{}", "not-json", '{"url":"https://external.invalid"}'])
def test_early_exit_and_invalid_readiness_fail_closed(line):
    with pytest.raises(RuntimeError):
        read_ready(SimpleNamespace(stdout=io.StringIO(line)), .1)


def test_health_cannot_ignore_exited_child():
    with pytest.raises(RuntimeError, match="exited"):
        wait_healthy(SimpleNamespace(poll=lambda: 73), "http://127.0.0.1:1", .1)


def test_owned_api_worker_startup_and_shutdown_remove_and_revoke_credentials():
    result = subprocess.run([sys.executable, str(ROOT / "tools/run_browser_verification.py"), "--smoke-only", "--probe-subprocess"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=110, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["mode"] == "STARTUP_SHUTDOWN_ONLY" and receipt["browser_exit_code"] is None
    assert receipt["server_exit_code"] == 0
    assert receipt["subprocess_probe"] == {"negative": "VIOLATION", "positive": "CONFORMS", "mocked": False}
    assert receipt["shutdown"] == {"worker_stopped": True, "credentials_revoked": True, "credentials_removed": True}
