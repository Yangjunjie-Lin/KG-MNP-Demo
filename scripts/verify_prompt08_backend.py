"""Real socket/HTTP SDK entry gate. Never substitutes fixture success for core."""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
import uvicorn

from kg_mnp.api.app import create_app
from kg_mnp.jobs.worker import JobWorker
from kg_mnp.sdk.errors import SDKError
from kg_mnp.sdk.http import HTTPClient
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration

ROOT = Path(__file__).resolve().parents[1]


def main():
    state = ROOT / "runtime" / ("prompt08-http-gate-" + uuid4().hex[:8])
    service = ApplicationService(ServiceConfiguration(str(state), domain_packs_root=str(ROOT / "domain_packs")))
    token, _ = service.tokens.create(principal_id="prompt08-test-human", principal_type="HUMAN", permissions={"*"},
                                     project_ids=set(), created_by="explicit-offline-test-bootstrap")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(service), host="127.0.0.1", port=port, log_level="error"))
    web = threading.Thread(target=server.run, daemon=True)
    stop = threading.Event()
    worker = threading.Thread(target=JobWorker(service.jobs, service).run_forever,
                              kwargs={"worker_id": "prompt08-real-worker", "stop": stop}, daemon=True)
    web.start()
    worker.start()
    url = f"http://127.0.0.1:{port}"
    report = {"backend_gate": "FAIL", "decision": "NO_GO_BACKEND_NOT_READY", "transport": "REAL_HTTP_SOCKET",
              "worker": "REAL_DURABLE_WORKER", "checks": [], "business_workflow": "NOT_COMPLETED"}
    try:
        deadline = time.monotonic() + 15
        while not server.started and web.is_alive() and time.monotonic() < deadline:
            stop.wait(0.05)
        if not server.started:
            raise RuntimeError("HTTP server failed to start; no unknown process was terminated")
        with httpx.Client(base_url=url, timeout=180, headers={"Authorization": f"Bearer {token}"}) as client:
            assert client.get("/health/live").json() == {"status": "ALIVE"}
            assert client.get("/api/v1/me").json()["principal_id"] == "prompt08-test-human"
            sdk = HTTPClient(url, token, client=client)
            packs = sdk.execute(OperationRequest("domain-pack.discover")).payload
            assert any(pack["pack_id"] == "minimal" and pack["availability"] == "AVAILABLE" for pack in packs["domain_packs"])
            created = sdk.execute(OperationRequest("project.create", parameters={"name": "HTTP backend gate",
                                                 "domain_pack": "minimal", "domain_pack_version": "0.1.0"}, idempotency_key="create-http"))
            project_id = created.payload["project_id"]
            assert created.payload["status"] == "VALID" and "root" not in created.payload
            assert sdk.execute(OperationRequest("project.validate", project_id)).payload["status"] == "VALID"
            assert sdk.execute(OperationRequest("registry.verify", project_id)).payload["status"] == "VALID"
            report.update(project_id=project_id, manifest_project_id=created.payload["manifest_project_id"])
            report["checks"].extend([{"name": name, "status": "PASS"} for name in ("identity", "minimal-pack-discovery", "real-workspace", "workspace-validation", "empty-registry-verification")])
            response = client.post(f"/api/v1/projects/{project_id}/sources", content=b"id,label\ndemo-1,Example\n", headers={"Content-Type": "text/csv"})
            report["checks"].append({"name": "source-upload-resource", "status": "FAIL", "http_status": response.status_code})
            try:
                sdk.execute(OperationRequest("source.register", project_id, {}, "register-http"))
            except SDKError as exc:
                report["checks"].append({"name": "source-registration-handler", "status": "FAIL", "code": exc.code, "http_status": exc.status_code})
            else:
                raise AssertionError("gate implementation must be extended through all downstream operations before PASS")
            report["missing_operations"] = [item["operation_id"] for item in service.capabilities(service.authenticate(f"Bearer {token}"))["capabilities"] if item["status"] == "NOT_IMPLEMENTED"]
            report["8B_browser_acceptance"] = "NOT_RUN_BACKEND_GATE_FAILED"
            report["8C_cross_domain_acceptance"] = "NOT_RUN_BACKEND_GATE_FAILED"
    finally:
        stop.set()
        server.should_exit = True
        web.join(timeout=10)
        worker.join(timeout=10)
        report["owned_processes_stopped"] = not web.is_alive() and not worker.is_alive()
        path = state / "backend-gate.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"report": str(path), **report}), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
