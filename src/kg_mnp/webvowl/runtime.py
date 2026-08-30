from __future__ import annotations

import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .policy import load_webvowl_policy
from .verifier import validate_runtime_policy


class WebVOWLRuntimeError(RuntimeError):
    pass


def runtime_descriptor(
    *, policy: Mapping[str, Any] | None = None, image_digest: str | None = None
) -> dict[str, Any]:
    value = dict(policy or load_webvowl_policy())
    validate_runtime_policy(policy=value)
    return {
        "contract_version": "1.0",
        "runtime_id": value["runtime_id"],
        "bind_host": value["network"]["bind_host"],
        "port": value["network"]["port"],
        "external_exposure": value["network"]["external_exposure"],
        "runtime_internet_access": value["network"]["runtime_internet_access"],
        "image_digest": image_digest,
    }


def start_webvowl_runtime(
    *,
    compose_file: Path,
    policy: Mapping[str, Any] | None = None,
    project_name: str = "kg-mnp-webvowl",
    dry_run: bool = False,
) -> subprocess.Popen[str] | None:
    value = dict(policy or load_webvowl_policy())
    validate_runtime_policy(policy=value)
    if dry_run:
        return None
    if value["network"]["bind_host"] != "127.0.0.1":
        raise WebVOWLRuntimeError("refusing non-loopback runtime")
    command = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "-p",
        project_name,
        "up",
        "--build",
        "--detach",
    ]
    try:
        subprocess.run(
            command,
            check=True,
            env={
                **__import__("os").environ,
                "DOCKER_BUILDKIT": "1",
                "WEBVOWL_PORT": "8080",
            },
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise WebVOWLRuntimeError(f"cannot start WebVOWL runtime: {exc}") from exc
    return None


def runtime_smoke(
    base_url: str = "http://127.0.0.1:8080", *, timeout: float = 30.0
) -> dict[str, Any]:
    import urllib.request

    started = time.monotonic()
    parsed = urlparse(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 8080
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        return {
            "status": "FAILED",
            "root_status": None,
            "converter_status": None,
            "checks": {},
            "errors": ["runtime smoke requires http://127.0.0.1:8080"],
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    checks = {}
    errors = []
    for path in ("/", "/serverTimeStamp"):
        try:
            with urllib.request.urlopen(base_url + path, timeout=5) as response:
                body = response.read(1024 * 1024).decode("utf-8", errors="replace")
                checks[path] = response.status == 200
                if path == "/":
                    checks["webvowl_identity"] = "WebVOWL" in body
        except (OSError, ValueError) as exc:
            checks[path] = False
            errors.append(str(exc))
    return {
        "status": "PASS" if all(checks.values()) else "FAILED",
        "root_status": 200 if checks.get("/") else None,
        "converter_status": 200 if checks.get("/serverTimeStamp") else None,
        "checks": checks,
        "errors": errors,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
