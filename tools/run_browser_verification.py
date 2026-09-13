"""Bounded startup, actual browser workflows, and owned-process-only shutdown."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def read_ready(server, timeout: float, expected_workspace=None) -> dict:
    """Do not let a silent/crashed child block the verifier on readline."""
    lines = queue.Queue()
    Thread(target=lambda: lines.put(server.stdout.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError("Synthetic browser server readiness deadline exceeded") from exc
    if not line:
        raise RuntimeError("Synthetic browser server exited before readiness")
    try:
        ready = json.loads(line)
        parsed = urlsplit(ready["url"])
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("not the owned loopback server")
        workspace = Path(ready["workspace"]).resolve(strict=True)
        credential = Path(ready["credential_path"])
        allowed_workspace = workspace.is_relative_to((ROOT / "runtime").resolve()) or (expected_workspace is not None and workspace == expected_workspace.resolve(strict=True))
        if not allowed_workspace or credential.is_symlink() or credential.resolve(strict=True) != workspace / "browser-test-credential.json":
            raise ValueError("not an owned synthetic credential")
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise RuntimeError("Invalid synthetic server readiness record") from exc
    return ready


def wait_healthy(server, url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Synthetic browser server exited during startup")
        try:
            with urlopen(url + "/healthz", timeout=min(1, max(.01, deadline-time.monotonic()))) as response:
                if json.load(response) == {"status": "ALIVE"}:
                    return
        except (URLError, TimeoutError, ValueError):
            pass
        time.sleep(.05)
    raise TimeoutError("Synthetic browser server health deadline exceeded")


def stop_owned(server, stop_file: Path, timeout: float = 60) -> int:
    """No port-based process search/kill; only this Popen handle is controlled."""
    try:
        if server.poll() is None:
            stop_file.touch(exist_ok=False)
            try:
                server.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
                raise RuntimeError("Owned server required forced shutdown; verification is incomplete") from None
        return server.returncode
    finally:
        for stream in (server.stdin, server.stdout):
            if stream:
                stream.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-only", action="store_true", help="verify startup/shutdown only, never claim Browser E2E")
    parser.add_argument("--startup-timeout", type=float, default=45)
    parser.add_argument("--probe-subprocess", action="store_true", help="include actual SHACL subprocess startup in smoke verification")
    parser.add_argument("--selected-test", choices=("security.e2e.ts", "arbitrary-pack.e2e.ts", "five-stage.e2e.ts", "ontology-io.e2e.ts", "zhigou-console.e2e.ts", "saved-evidence.e2e.ts", "mnp-readback.e2e.ts", "mixed", "minimal", "forestry", "mnp"), help="bounded incremental check only, never full browser acceptance")
    parser.add_argument("--existing-upgrade-workspace", type=Path)
    args = parser.parse_args()
    if not 0 < args.startup_timeout <= 120:
        parser.error("startup timeout must be in (0, 120]")
    directory = ROOT / "runtime_logs/p09/browser-runs" / ("managed-" + uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    receipt = {"mode": "STARTUP_SHUTDOWN_ONLY" if args.smoke_only else "SELECTED_BROWSER_E2E" if args.selected_test else "REAL_BROWSER_E2E", "selected_test": args.selected_test, "status": "FAIL"}
    ready = None
    stop_file = directory / "stop-requested"
    try:
        with (directory / "server.log").open("w", encoding="utf-8") as log:
            command = [sys.executable, str(ROOT / "tools/run_workbench_test_server.py"), "--stop-file", str(stop_file)]
            if args.existing_upgrade_workspace:
                if args.selected_test not in {"saved-evidence.e2e.ts", "mnp-readback.e2e.ts"}:
                    raise ValueError("Existing synthetic workspace is only for read-only saved evidence inspection")
                command.extend(["--existing-upgrade-workspace", str(args.existing_upgrade_workspace)])
            # Only the full/arbitrary-pack browser scenario needs a copied
            # fourth pack. Lifecycle smoke still runs the same real validators.
            if not args.smoke_only and args.selected_test in {None, "arbitrary-pack.e2e.ts"}:
                command.append("--temporary-pack")
            if args.probe_subprocess:
                command.append("--probe-subprocess")
            server = subprocess.Popen(command,
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log, text=True,
                encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                start = time.monotonic()
                ready = read_ready(server, args.startup_timeout, args.existing_upgrade_workspace)
                wait_healthy(server, ready["url"], args.startup_timeout)
                receipt["startup_seconds"] = time.monotonic() - start
                environment = {**os.environ, "KG_MNP_BROWSER_URL": ready["url"], "KG_MNP_BROWSER_CREDENTIAL": ready["credential_path"],
                    "KG_MNP_BROWSER_EVIDENCE": str(directory), "KG_MNP_TEST_PYTHON": sys.executable}
                if args.existing_upgrade_workspace:
                    environment["ZHIGOU_SAVED_EVIDENCE"] = "1"
                    environment["ZHIGOU_SAVED_WORKSPACE"] = str(args.existing_upgrade_workspace.resolve())
                receipt["browser_exit_code"] = None
                if not args.smoke_only:
                    npm = "npm.cmd" if os.name == "nt" else "npm"
                    command = [npm, "--prefix", "workbench", "run", "test:e2e"]
                    if args.selected_test in {"mixed", "minimal", "forestry", "mnp"}:
                        command.extend(["--", "minimal.e2e.ts", "--grep", "real browser " + args.selected_test])
                    elif args.selected_test:
                        command.extend(["--", args.selected_test])
                    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
                    receipt["browser_exit_code"] = result.returncode
                receipt["status"] = "PASS" if receipt["browser_exit_code"] in {None, 0} else "FAIL"
            finally:
                receipt["server_exit_code"] = stop_owned(server, stop_file)
                if receipt["server_exit_code"]:
                    receipt["status"] = "FAIL"
        if ready:
            if args.probe_subprocess:
                receipt["subprocess_probe"] = json.loads((Path(ready["workspace"]) / "subprocess-probe.json").read_bytes())
            shutdown = json.loads((Path(ready["workspace"]) / "browser-server-shutdown.json").read_bytes())
            receipt["shutdown"] = shutdown
            if not all(shutdown.get(key) is True for key in ("worker_stopped", "credentials_revoked", "credentials_removed")):
                receipt["status"] = "FAIL"
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        receipt["status"] = "FAIL"
        # Never include child stdout/readiness bodies or credential values.
        receipt["error_type"] = type(exc).__name__
    finally:
        receipt["artifacts"] = {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}
        (directory / "managed-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps({"evidence": str(directory.relative_to(ROOT)), **receipt}), flush=True)
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
