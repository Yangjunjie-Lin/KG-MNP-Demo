"""Owned loopback test server/worker using synthetic identities, never production."""
from __future__ import annotations

import argparse
import json
import socket
import tempfile
from pathlib import Path
from threading import Event, Thread

import uvicorn

from kg_mnp.api.app import create_app
from kg_mnp.contracts.document_io import atomic_write_json
from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    runtime = root / "runtime"
    runtime.mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="p09-browser-", dir=runtime))
    sock = socket.socket()
    sock.bind(("127.0.0.1", args.port))
    sock.listen()
    port = sock.getsockname()[1]
    service = ApplicationService(ServiceConfiguration(str(workspace), port=port,
        domain_packs_root=str(root / "domain_packs"), workbench_root=str(root / "workbench/dist"),
        allow_insecure_loopback_session=True, review_profile="DEVELOPMENT_SINGLE_REVIEWER",
        reasoner_jar=str(root / "third_party/downloads/robot-1.9.7.jar")))
    token, _ = service.tokens.create(principal_id="synthetic-browser-human", principal_type="HUMAN",
                                    permissions={"*"}, project_ids=set(), created_by="explicit-synthetic-browser-test")
    credentials = workspace / "browser-test-credential.json"
    atomic_write_json(credentials, {"token": token})
    stop = Event()
    worker = Thread(target=JobWorker(service.jobs, service).run_forever, kwargs={"worker_id":"browser-test-worker", "stop":stop}, daemon=True)
    worker.start()
    print(json.dumps({"url":f"http://127.0.0.1:{port}", "credential_path":str(credentials), "workspace":str(workspace)}), flush=True)
    try:
        uvicorn.Server(uvicorn.Config(create_app(service), access_log=False, log_level="warning")).run(sockets=[sock])
    finally:
        stop.set()
        worker.join(35)
        sock.close()
        credentials.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
