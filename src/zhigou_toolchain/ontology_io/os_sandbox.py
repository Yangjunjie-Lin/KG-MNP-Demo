"""WSL/bubblewrap minimal mounts + network namespace for ontology generation.

The Windows parent performs only bounded model transport. Generation receives
one public job and cannot see the Windows drive, user home, scorer or siblings.
"""
from __future__ import annotations

import hashlib
import json
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from time import monotonic

from zhigou_toolchain.contracts.canonical import semantic_hash

from .contracts import Protocol
from .live_broker import dispatch

DISTRO = "Ubuntu-24.04"
VENV = "/home/yangjunjie/.cache/zhigou-ontology-eval-20260914/venv"


def wsl_path(path):
    value = Path(path).resolve().as_posix()
    if len(value) < 3 or value[1:3] != ":/":
        raise ValueError("ABSOLUTE_WINDOWS_WORKSPACE_PATH_REQUIRED")
    return "/mnt/" + value[0].lower() + value[2:]


def stage_code(root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for package in ("zhigou_toolchain", "kg_mnp"):
        for path in (root / "src" / package).rglob("*"):
            rel = path.relative_to(root / "src")
            if not path.is_file() or "__pycache__" in rel.parts or "/resources/tutorial/" in rel.as_posix():
                continue
            if path.is_symlink():
                raise ValueError("WORKER_CODE_SYMLINK_FORBIDDEN")
            if path.suffix not in {".py", ".json", ".yaml", ".yml", ".ttl", ".rq"}:
                continue
            target = output / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            files[rel.as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()
    return {"files": files, "sha256": semantic_hash(files), "policy": "SOURCE_AND_CONTRACTS_NO_TESTS_NO_TUTORIAL_ANSWERS_NO_DATASETS"}


def command(code, job_input, job_output, reasoner, *, extra=()):
    return ["wsl", "-d", DISTRO, "--exec", "/usr/bin/timeout", "--kill-after=5s", "900s", "bwrap", "--unshare-all", "--unshare-user", "--die-with-parent", "--new-session",
        "--cap-drop", "ALL", "--disable-userns", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
        "--tmpfs", "/tmp", "--dir", "/home", "--dir", "/etc", "--dir", "/opt",
        "--ro-bind", "/etc/java-21-openjdk", "/etc/java-21-openjdk",
        "--ro-bind", VENV, "/runtime", "--ro-bind", wsl_path(code), "/code",
        "--ro-bind", wsl_path(job_input), "/input", "--bind", wsl_path(job_output), "/out",
        "--ro-bind", wsl_path(reasoner), "/opt/robot.jar", "--chdir", "/out", "--clearenv",
        "--setenv", "PATH", "/usr/lib/jvm/java-21-openjdk-amd64/bin:/runtime/bin:/usr/bin",
        "--setenv", "PYTHONPATH", "/code", "--setenv", "PYTHONDONTWRITEBYTECODE", "1", "--setenv", "PYTHONUTF8", "1",
        "--setenv", "PYTHONNOUSERSITE", "1", "--setenv", "LANG", "C.UTF-8", "--setenv", "HOME", "/home",
        "--setenv", "PYTHONHASHSEED", "0", "--setenv", "JAVA_TOOL_OPTIONS", "-Xmx512m -XX:MaxMetaspaceSize=256m -XX:CompressedClassSpaceSize=128m -XX:ReservedCodeCacheSize=64m -XX:ActiveProcessorCount=2",
        "--setenv", "TZ", "UTC", "--", "/runtime/bin/python", "-m", "zhigou_toolchain.ontology_io.sandbox_worker", *extra]


def verify_canary(code, root, reasoner):
    root = Path(root)
    public, out, scoring = root / "canary-input", root / "canary-output", root / "scoring-canary"
    for path in (public, out, scoring):
        path.mkdir(parents=True, exist_ok=False)
    sentinel = scoring / "gold.txt"
    sentinel.write_text("SYNTHETIC_GOLD_ACCESS_CANARY", encoding="utf-8")
    (public / "public-input.txt").write_text("PUBLIC_CANARY_INPUT", encoding="utf-8")
    forbidden = [wsl_path(sentinel), "/input/../scoring-canary/gold.txt", "/home/yangjunjie/.bashrc",
        "/mnt/c/Windows/System32/config/SYSTEM", "/proc/1/root" + wsl_path(sentinel)]
    result = subprocess.run(command(code, public, out, reasoner, extra=["--canary", "--forbidden", *forbidden]),
        capture_output=True, timeout=60, check=False)
    if result.returncode:
        raise ValueError("BWRAP_CANARY_PROCESS_FAILED:" + result.stderr.decode(errors="replace")[-1500:])
    report = json.loads(result.stdout)
    host_namespace = subprocess.check_output(["wsl", "-d", DISTRO, "--exec", "readlink", "/proc/self/ns/net"], timeout=15).decode().strip()
    report["host_network_namespace"] = host_namespace
    report["network_namespace_distinct"] = report["network_namespace"] != host_namespace
    if not report["passed"] or not report["network_namespace_distinct"]:
        raise ValueError("BWRAP_CANARY_ACCESS_OR_NETWORK_NOT_DENIED")
    report.update(policy="WSL_BWRAP_UNSHARE_ALL_MINIMAL_READONLY_MOUNTS_IPC_BROKER", forbidden_host_file_exists=sentinel.is_file())
    return report


def run_job(job, *, code, directory, reasoner, ledger, job_id, endpoint_sha256, model_timeout=150, wall_timeout=900):
    directory = Path(directory)
    public, output = directory / "input", directory / "output"
    public.mkdir(parents=True, exist_ok=False)
    output.mkdir()
    # The protocol's path is a task-independent runtime substitution with a
    # separately verified, fixed JAR digest. Every system gets this same path.
    protocol = Protocol.model_validate(job["protocol"])
    if protocol.kernel_profile:
        protocol = protocol.model_copy(update={"kernel_profile": protocol.kernel_profile.model_copy(update={"reasoner_jar": "/opt/robot.jar"})})
    job = {**job, "protocol": protocol.model_dump(mode="json")}
    (public / "job.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    process = subprocess.Popen(command(code, public, output, reasoner), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    stdout, stdin, error_stream = process.stdout, process.stdin, process.stderr
    assert stdout is not None and stdin is not None and error_stream is not None
    messages = queue.Queue()

    def read_stdout():
        try:
            while True:
                line = stdout.readline(4_000_001)
                if not line:
                    break
                messages.put(line)
        finally:
            messages.put(None)

    stderr = []

    def read_stderr():
        for line in error_stream:
            if sum(map(len, stderr)) < 200000:
                stderr.append(line)

    threading.Thread(target=read_stdout, daemon=True).start()
    threading.Thread(target=read_stderr, daemon=True).start()
    started, index, done = monotonic(), 0, None
    try:
        while monotonic() - started < wall_timeout:
            try:
                line = messages.get(timeout=max(.01, min(5, wall_timeout - (monotonic() - started))))
            except queue.Empty:
                continue
            if line is None:
                break
            if len(line) > 4_000_000:
                raise ValueError("SANDBOX_MESSAGE_LIMIT")
            message = json.loads(line)
            if message.get("op") == "done":
                done = message
                break
            if message.get("op") != "model" or index >= min(protocol.budget.max_calls, job.get("max_calls", protocol.budget.max_calls)):
                raise ValueError("SANDBOX_BROKER_OPERATION_OR_CALL_LIMIT")
            index += 1
            reply = dispatch(message["request"], protocol=protocol, ledger=ledger, job_id=job_id,
                request_id=f"{job_id}:call-{index}", directory=directory / "calls" / str(index),
                endpoint_sha256=endpoint_sha256, timeout=min(model_timeout, int(wall_timeout - (monotonic() - started))), code=code)
            stdin.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdin.flush()
        if done is None:
            raise TimeoutError("SANDBOX_FAILED_OR_WALLTIME_EXCEEDED")
        process.wait(timeout=15)
        return {"status": done["status"], "done": done, "calls": index, "wall_seconds": monotonic() - started,
            "result_path": str(output / "result/result.json"), "effective_protocol": protocol.model_dump(mode="json")}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        (directory / "worker.stderr").write_text("".join(stderr), encoding="utf-8")
