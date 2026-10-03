"""Owned loopback test server/worker using synthetic identities, never production."""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import tempfile
from pathlib import Path
from threading import Event, Thread


def main():
    # Windows spawn re-imports this launcher for each isolated validator/query.
    # Children need the target validator, not another eager import of the full
    # API/service/DTO stack. Keep server-only imports in the guarded entry point.
    import uvicorn

    from zhigou_toolchain.api.app import create_app
    from zhigou_toolchain.contracts.document_io import atomic_write_json
    from zhigou_toolchain.jobs.worker import JobWorker
    from zhigou_toolchain.services.facade import ApplicationService
    from zhigou_toolchain.services.models import ServiceConfiguration

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--existing-upgrade-workspace", type=Path, help="read an explicitly generated completed upgrade test workspace")
    parser.add_argument("--temporary-pack", action="store_true")
    parser.add_argument("--stop-file", type=Path, help="owned local test-control marker; never a public API")
    parser.add_argument("--probe-subprocess", action="store_true", help="exercise actual isolated validation before browser readiness")
    parser.add_argument("--record-step-content", action="store_true", help="explicitly retain redacted before/after modeling content in this synthetic workspace")
    parser.add_argument("--mock-scenario-model", action="store_true", help="explicit synthetic scene browser only: original clients with independent MockTransport")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    runtime = root / "runtime"
    runtime.mkdir(exist_ok=True)
    if args.existing_upgrade_workspace:
        workspace = args.existing_upgrade_workspace.resolve(strict=True)
        generated_pytest = workspace.parent.name.startswith("pytest-") and workspace.parent.parent.name.startswith("pytest-of-")
        retained_upgrade = workspace.is_relative_to((root / "runtime_reports").resolve())
        owned_browser = workspace.is_relative_to((root / "runtime").resolve()) and workspace.name.startswith("p09-browser-")
        if not owned_browser and (workspace.name not in {"upgrade-hr0", "upgrade-forest0"} or not (generated_pytest or retained_upgrade)):
            raise ValueError("Only completed generated upgrade test workspaces may be opened")
    else:
        workspace = Path(tempfile.mkdtemp(prefix="p09-browser-", dir=runtime))
    packs=root/"domain_packs"
    if args.temporary_pack:
        import yaml

        from zhigou_toolchain.domain_packs.locking import generate_pack_lock
        from zhigou_toolchain.domain_packs.validation import load_domain_pack_manifest
        packs=workspace/"test-packs"
        shutil.copytree(root/"domain_packs",packs)
        temporary=packs/"arbitrary-validation-pack"
        shutil.copytree(packs/"minimal",temporary)
        manifest=yaml.safe_load((temporary/"pack.yaml").read_text(encoding="utf8"))
        manifest["pack_id"]="arbitrary-validation-pack"
        manifest["display_name"]="临时通用性验证领域包"
        (temporary/"pack.yaml").write_text(yaml.safe_dump(manifest,allow_unicode=True,sort_keys=False),encoding="utf8")
        generate_pack_lock(load_domain_pack_manifest(temporary))
    sock = socket.socket()
    sock.bind(("127.0.0.1", args.port))
    sock.listen()
    port = sock.getsockname()[1]
    service = ApplicationService(ServiceConfiguration(str(workspace), port=port,
        domain_packs_root=str(packs), workbench_root=str(root / "workbench/dist"),
        allow_insecure_loopback_session=True, review_profile="DEVELOPMENT_SINGLE_REVIEWER",
        modeling_audit_content_enabled=args.record_step_content,
        ontology_trace_enabled=args.mock_scenario_model,
        reasoner_jar=str(root / "third_party/downloads/robot-1.9.7.jar")))
    scenario_spy, scenario_patch = None, None
    if args.mock_scenario_model:
        from importlib.util import module_from_spec, spec_from_file_location
        from unittest.mock import patch
        spec = spec_from_file_location("scenario_transport_witness", root / "tests/upgrade/expert_spy.py")
        assert spec is not None and spec.loader is not None
        witness_module = module_from_spec(spec)
        spec.loader.exec_module(witness_module)
        scenario_spy = witness_module.ExpertSpy(revise_scope=True)
        scenario_patch = patch("zhigou_toolchain.services.modeling_expert.configured_client", scenario_spy.client)
        scenario_patch.start()
    token, human = service.tokens.create(principal_id="synthetic-browser-human", principal_type="HUMAN",
                                    permissions={"*"}, project_ids=set(), created_by="explicit-synthetic-browser-test")
    viewer_token, viewer = service.tokens.create(principal_id="synthetic-isolated-viewer", principal_type="HUMAN",
        permissions={"project:read", "source:read", "package:read", "job:read"}, project_ids=set(), created_by="explicit-synthetic-browser-test")
    credentials = workspace / "browser-test-credential.json"
    atomic_write_json(credentials, {"token": token, "viewer_token": viewer_token})
    stop = Event()
    worker = Thread(target=JobWorker(service.jobs, service).run_forever, kwargs={"worker_id":"browser-test-worker", "stop":stop}, daemon=True)
    # A closed browser may leave read-only ASGI requests in flight. Bound their
    # teardown, then execute the existing credential revocation and Worker
    # drain in finally. This does not change any modeling/review timeout.
    server = uvicorn.Server(uvicorn.Config(create_app(service), access_log=False, log_level="warning", timeout_graceful_shutdown=10))
    if args.stop_file:
        control = args.stop_file.resolve()
        if not control.is_relative_to((root / "runtime_logs/p09/browser-runs").resolve()):
            raise ValueError("test stop marker must remain in owned browser evidence")
        def watch_owner():
            # Never block on stdin: Windows spawn can inherit a blocked standard
            # input read and hang before Process.start returns.
            while not stop.wait(.1):
                if control.exists():
                    stop.set()
                    server.should_exit = True
        Thread(target=watch_owner, daemon=True).start()
    worker.start()
    try:
        if args.probe_subprocess:
            from rdflib import Graph, Literal, URIRef

            from zhigou_toolchain.semantic_kernel.validators.shacl import validate_shacl
            data = Graph().parse(data="<urn:item> a <urn:Thing> .", format="turtle")
            shapes = Graph().parse(data='@prefix sh: <http://www.w3.org/ns/shacl#> . <urn:Shape> a sh:NodeShape; sh:targetClass <urn:Thing>; sh:property <urn:Field> . <urn:Field> sh:path <urn:label>; sh:minCount 1 .', format="turtle")
            failed, _ = validate_shacl(data_graph=data, shapes_graph=shapes, ontology_graph=Graph(), max_seconds=20)
            assert failed["status"] == "VIOLATION"
            data.add((URIRef("urn:item"), URIRef("urn:label"), Literal("Synthetic")))
            passed, _ = validate_shacl(data_graph=data, shapes_graph=shapes, ontology_graph=Graph(), max_seconds=20)
            assert passed["status"] == "CONFORMS"
            atomic_write_json(workspace / "subprocess-probe.json", {"negative": failed["status"], "positive": passed["status"], "mocked": False})
        print(json.dumps({"url":f"http://127.0.0.1:{port}", "credential_path":str(credentials), "workspace":str(workspace)}), flush=True)
        server.run(sockets=[sock])
    finally:
        stop.set()
        # Revoke before waiting so in-flight work cannot publish afterwards.
        service.tokens.revoke(human.token_id)
        service.tokens.revoke(viewer.token_id)
        worker.join(35)
        if scenario_spy is not None:
            from zhigou_toolchain.services.modeling_audit import read_events
            from zhigou_toolchain.services.projects import list_projects
            recorded = sum(1 for project in list_projects(service.root) for job in service.jobs.list_project(project.project_id)
                for event in read_events(service, job) if event["phase"] == "AFTER" and event["metadata"].get("kind") == "MODEL"
                and event["metadata"].get("dispatch_status") == "TRANSPORT_ATTEMPTED")
            atomic_write_json(workspace / "browser-scenario-http-witness.json", {"nature": "MOCK_TRANSPORT_NOT_LIVE",
                "physical_requests": len(scenario_spy.requests), "recorded_requests": recorded, "requests": scenario_spy.requests,
                "counts_match": recorded == len(scenario_spy.requests)})
            scenario_patch.stop()
        sock.close()
        credentials.unlink(missing_ok=True)
        atomic_write_json(workspace / "browser-server-shutdown.json", {
            "credentials_removed": not credentials.exists(), "credentials_revoked": True,
            "worker_stopped": not worker.is_alive(),
        })
        if worker.is_alive():
            raise SystemExit("Synthetic Worker did not stop within shutdown deadline")


if __name__ == "__main__":
    main()
