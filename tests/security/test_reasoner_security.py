from __future__ import annotations

import subprocess
from pathlib import Path

from kg_mnp.semantic_kernel.reasoner import run_hermit

ROOT = Path(__file__).resolve().parents[2]


def test_reasoner_uses_argument_arrays_without_shell_or_workspace_executable(monkeypatch) -> None:
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return subprocess.CompletedProcess(arguments, 1, stdout=b"", stderr=b"failed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_hermit(b"<urn:s> <urn:p> <urn:o> .\n", reasoner_jar=ROOT / "third_party/downloads/robot-1.9.7.jar", timeout_seconds=5, max_output_bytes=1024)
    assert result["status"] == "FAILED"
    assert len(calls) == 2
    assert all(isinstance(arguments, list) and kwargs["shell"] is False for arguments, kwargs in calls)


def test_reasoner_timeout_is_bounded_and_reported(monkeypatch) -> None:
    calls = 0

    def fake_run(arguments, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout=b"",
                stderr=b'openjdk version "17.0.1"',
            )
        raise subprocess.TimeoutExpired(arguments, kwargs["timeout"], output=b"bounded")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_hermit(
        b"<urn:s> <urn:p> <urn:o> .\n",
        reasoner_jar=ROOT / "third_party/downloads/robot-1.9.7.jar",
        timeout_seconds=1,
        max_output_bytes=4,
    )
    assert result["status"] == "TIMEOUT"
    assert result["timeout"] is True
    assert result["diagnostics"] == b"boun"


def test_reasoner_zero_exit_without_output_fails_closed(monkeypatch) -> None:
    calls = 0

    def fake_run(arguments, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(
            arguments,
            0,
            stdout=b"" if calls == 1 else b"no output artifact",
            stderr=b'openjdk version "17.0.1"' if calls == 1 else b"",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_hermit(
        b"<urn:s> <urn:p> <urn:o> .\n",
        reasoner_jar=ROOT / "third_party/downloads/robot-1.9.7.jar",
        timeout_seconds=5,
        max_output_bytes=8,
    )
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 0
    assert len(result["diagnostics"]) == 8
