"""Single pinned, local-only ROBOT/HermiT subprocess primitive."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .snapshot import HERMIT_POM, HERMIT_VERSION, ROBOT_SHA256


def hermit_version(jar: Path) -> str:
    try:
        with zipfile.ZipFile(jar) as archive:
            content = archive.read(HERMIT_POM).decode("iso-8859-1")
    except (OSError, KeyError, zipfile.BadZipFile):
        return "UNKNOWN"
    for line in content.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "version":
            return value.strip()
    return "UNKNOWN"


def verify_reasoner_bundle(path: Path | str) -> Path:
    jar = Path(path).resolve(strict=True)
    if not jar.is_file() or jar.is_symlink():
        raise ValueError("reasoner bundle is not a regular local file")
    if hashlib.sha256(jar.read_bytes()).hexdigest() != ROBOT_SHA256:
        raise ValueError("ROBOT JAR digest mismatch")
    if hermit_version(jar) != HERMIT_VERSION:
        raise ValueError("HermiT dependency version mismatch")
    return jar


def run_hermit(
    input_bytes: bytes,
    *,
    reasoner_jar: Path | str | None,
    timeout_seconds: int,
    max_output_bytes: int,
) -> dict[str, Any]:
    if reasoner_jar is None:
        return {"status": "REASONER_UNAVAILABLE", "exit_code": None, "timeout": False, "java_major": None, "diagnostics": b""}
    jar = verify_reasoner_bundle(reasoner_jar)
    status, exit_code, timed_out, java_major, diagnostics = "FAILED", None, False, None, b""
    with tempfile.TemporaryDirectory(prefix="kg-mnp-hermit-") as directory:
        input_path = Path(directory) / "input.nt"
        output_path = Path(directory) / "reasoned.owl"
        input_path.write_bytes(input_bytes)
        try:
            version = subprocess.run(["java", "-version"], capture_output=True, check=False, shell=False, timeout=10)
            match = re.search(rb'version "([0-9]+)', version.stderr + version.stdout)
            java_major = int(match.group(1)) if match else None
            process = subprocess.run(
                ["java", "-jar", str(jar), "reason", "--input", str(input_path), "--reasoner", "hermit", "--equivalent-classes-allowed", "all", "--output", str(output_path)],
                capture_output=True, check=False, shell=False, timeout=timeout_seconds,
            )
            exit_code = process.returncode
            diagnostics = (process.stdout + b"\n" + process.stderr)[:max_output_bytes]
            if process.returncode == 0 and output_path.is_file():
                status = "CONSISTENT"
            elif re.search(rb"(?:ontology\s+is\s+inconsistent|inconsistent\s+ontology|inconsistency)", diagnostics, re.IGNORECASE):
                status = "INCONSISTENT"
        except subprocess.TimeoutExpired as exc:
            status, timed_out = "TIMEOUT", True
            diagnostics = ((exc.stdout or b"") + (exc.stderr or b""))[:max_output_bytes]
        except OSError as exc:
            status = "REASONER_UNAVAILABLE"
            diagnostics = str(exc).encode()[:max_output_bytes]
    return {"status": status, "exit_code": exit_code, "timeout": timed_out, "java_major": java_major, "diagnostics": diagnostics}
