"""Run with an isolated installed Python (-I), never with repository src on sys.path."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

import kg_mnp
from kg_mnp.contracts import ContractCatalog
from kg_mnp.semantic_kernel.packaging.archive import verify_kgop
from kg_mnp.semantic_kernel.policy import load_compiler_policy
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--packs", type=Path, required=True)
    parser.add_argument("--historical-package", type=Path, required=True)
    args = parser.parse_args()
    args.packs = args.packs.resolve(strict=True)
    args.historical_package = args.historical_package.resolve(strict=True)
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    # An editable install/host site-package inheritance cannot satisfy this gate.
    assert Path(kg_mnp.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    assert sys.prefix != sys.base_prefix
    assert not any(Path(p).name == "src" for p in sys.path)
    assert len(ContractCatalog.load().specs) >= 117
    assert load_compiler_policy()["compiler_version"] == "0.5.1"
    historical = verify_kgop(args.historical_package)
    with socket.socket() as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        port = probe_socket.getsockname()[1]
    workspace = directory / "workspace"
    service = ApplicationService(ServiceConfiguration(str(workspace), port=port,
        domain_packs_root=str(args.packs), allow_insecure_loopback_session=True))
    token, principal = service.tokens.create(principal_id="installed-synthetic-human", principal_type="HUMAN",
        permissions={"*"}, project_ids=set(), created_by="isolated-install-probe")
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"} and not key.startswith("KG_MNP_")}
    env.update(KG_MNP_DOMAIN_PACKS_ROOT=str(args.packs), KG_MNP_SERVICE_PORT=str(port), KG_MNP_ALLOW_INSECURE_LOOPBACK_SESSION="true")
    python = sys.executable
    if os.name == "nt" and sys.executable != getattr(sys, "_base_executable", sys.executable):
        # Same redirector bypass as CPython multiprocessing (bpo-35797): the
        # owned Popen PID is the interpreter, not a venv launcher process.
        python = sys._base_executable
        env["__PYVENV_LAUNCHER__"] = sys.executable
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    commands = []
    server = None

    def start(log):
        process = subprocess.Popen([python, "-I", "-m", "kg_mnp", "service", "serve", "--workspace", str(workspace)],
            cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        commands.append({"command": "installed service serve", "pid": process.pid})
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            assert process.poll() is None, "Owned installed API exited during startup"
            try:
                if httpx.get(url + "/healthz", timeout=1).status_code == 200:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(.05)
        process.terminate()
        process.wait(timeout=10)
        raise AssertionError("Installed API startup deadline exceeded")

    def stop(process):
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
                raise AssertionError("Owned installed API did not stop") from None
        if process:
            with socket.socket() as stopped_socket:
                stopped_socket.settimeout(1)
                assert stopped_socket.connect_ex(("127.0.0.1", port)) != 0, "API remained reachable after owned process shutdown"

    def worker():
        result = subprocess.run([python, "-I", "-m", "kg_mnp", "service", "worker", "--workspace", str(workspace), "--once"],
            cwd=directory, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False, creationflags=flags)
        assert result.returncode == 0, "Installed Worker returned failure"
        observed = json.loads(result.stdout)
        commands.append({"command": "installed worker --once", "exit_code": result.returncode, "status": observed["status"]})
        assert observed["status"] == "SUCCEEDED"

    url = f"http://127.0.0.1:{port}"
    try:
        with (directory / "api.log").open("wb") as log:
            server = start(log)
            with httpx.Client(base_url=url, timeout=90) as http:
                assert http.get("/healthz").json() == {"status": "ALIVE"}
                assert http.get("/api/v1/projects").status_code == 401
                assert http.get("/api/v1/absent").status_code == 404
                index = http.get("/")
                assert index.status_code == 200 and "text/html" in index.headers["content-type"]
                assert http.get("/projects/synthetic/modeling").content == index.content
                assert http.get("/service-projects.json").content == index.content
                # An occupied port must fail without affecting the original server.
                conflict = subprocess.run([python, "-I", "-m", "kg_mnp", "service", "serve", "--workspace", str(workspace)],
                    cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=30, check=False, creationflags=flags)
                assert conflict.returncode != 0 and server.poll() is None
                login = http.post("/api/v1/session", headers={"Authorization": f"Bearer {token}", "Origin": url})
                assert login.status_code == 200 and "HttpOnly" in login.headers["set-cookie"]
                http.headers.update({"Origin": url, "X-CSRF-Token": login.json()["csrf_token"]})
                project = http.post("/api/v1/projects", json={"name": "安装验证", "domain_pack": "minimal", "domain_pack_version": "0.1.0"})
                assert project.status_code == 200
                project_id = project.json()["project_id"]
                payload = b'{"code":"SYNTH-INSTALL-1","label":"Synthetic install"}'
                upload_headers = {"Content-Type": "application/json", "X-Filename": "synthetic.json", "Idempotency-Key": "installed-upload-1"}
                accepted = http.post(f"/api/v1/projects/{project_id}/sources", content=payload, headers=upload_headers)
                assert accepted.status_code == 202
                job_id = accepted.json()["job_id"]
                worker()
                job = http.get(f"/api/v1/jobs/{job_id}").json()
                assert job["status"] == "SUCCEEDED"
                source_id = job["result"]["source"]["source_id"]
                source_url = f"/api/v1/projects/{project_id}/sources/{source_id}/content"
                assert http.get(source_url).content == payload
                assert httpx.get(url + source_url, timeout=15).status_code == 401
                # A new OS process reads the same durable Job and idempotency map.
                stop(server)
                server = start(log)
                assert http.get(f"/api/v1/jobs/{job_id}").json()["status"] == "SUCCEEDED"
                replay = http.post(f"/api/v1/projects/{project_id}/sources", content=payload, headers=upload_headers)
                assert replay.status_code == 202 and replay.json()["job_id"] == job_id
                changed = http.post(f"/api/v1/projects/{project_id}/sources", content=payload+b" ", headers=upload_headers)
                assert changed.status_code == 409
                doctor = http.get("/api/v1/doctor")
                assert doctor.status_code == 200
                # Missing Reasoner is deliberately not filled by a host file or download.
                from kg_mnp.semantic_kernel.snapshot import build_compiler_snapshot
                snapshot = build_compiler_snapshot(load_compiler_policy())
                assert snapshot["reasoner_bundle"]["availability"] == "UNAVAILABLE"
        result = {"status": "PASS", "installed_version": kg_mnp.__version__, "compiler_version": "0.5.1",
            "historical_package": historical, "project_id": project_id, "job_id": job_id, "source_id": source_id,
            "source_sha256": hashlib.sha256(payload).hexdigest(), "commands": commands,
            "checks": ["installed-contract-policy", "bundled-spa-deep-refresh", "api-401-404", "opaque-session", "port-conflict-no-kill",
                "separate-worker", "authorized-download", "process-restart-job", "idempotent-replay", "changed-body-conflict", "missing-reasoner-honest"]}
    finally:
        stop(server)
        service.tokens.revoke(principal.token_id)
    (directory / "probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
