"""Maintain the single requirement ledger and reproduce fixed-source history audit."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

from kg_mnp.contracts.document_io import atomic_write_json
from kg_mnp.services.operations import HANDLERS, build_operation_catalog

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "9da17d126cb37166ff06084080770108da20afbe"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    baseline = json.loads((ROOT / "docs/verification/prompt-08-service-coverage.json").read_bytes())
    from tests.refactor._historical_freeze import PROTECTED_ROOTS, SELF_PATH
    archive = subprocess.run(["git", "archive", SOURCE, *[p for p in PROTECTED_ROOTS if p != "workbench"]],
                             cwd=ROOT, capture_output=True, check=True).stdout
    digest, count = hashlib.sha256(), 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for entry in sorted(tree.getmembers(), key=lambda item: item.name):
            if not entry.isfile() or entry.name == SELF_PATH:
                continue
            data = tree.extractfile(entry).read()
            if b"\0" not in data:
                data = data.replace(b"\r\n", b"\n")
            digest.update(entry.name.encode() + b"\0" + hashlib.sha256(data).digest() + b"\n")
            count += 1
    assert (count, digest.hexdigest()) == (1498, "595558b7b32f0b64cd84729349dc81aae58dde6bc93624188646766727ce69cd")
    from tests.refactor import _historical_freeze as historical
    heads = [getattr(historical, f"PROMPT{index:02d}_HEAD_SHA") for index in range(1, 9)]
    for head in heads:
        subprocess.run(["git", "merge-base", "--is-ancestor", head, SOURCE], cwd=ROOT, check=True)
    catalog = build_operation_catalog()
    ledger_path = ROOT / "docs/verification/final-requirements.json"
    prior = json.loads(ledger_path.read_bytes()) if ledger_path.exists() else {}
    previous = {item["requirement_id"]: item for item in prior.get("requirements", [])}
    requirements = []
    for row in baseline["operations"]:
        name = row["operation_id"]
        item = previous.get(name, {"requirement_id": name, "source_requirement": "P9 original 53-operation baseline",
                                  "core_required": not name.startswith(("integration.", "workflow.", "visualization.")),
                                  "baseline_status": row["status"], "cli": "kg-mnp service call " + name,
                                  "sdk": "LocalClient.execute / HTTPClient.execute", "ui": "NOT_IMPLEMENTED",
                                  "positive_tests": [], "negative_tests": [], "commits": []})
        item.update({"implementation": HANDLERS.get(name), "maps_to": name,
                     "api": row["api_route"], "execution_mode": catalog[name].execution_mode,
                     "missing": [] if name in HANDLERS else ["typed service-to-core handler", "positive workflow test"],
                     "status": item.get("status", "IMPLEMENTED_NOT_VERIFIED") if name in HANDLERS else "OPEN",
                     "blocker": None if name in HANDLERS else "local implementation missing; not an external integration blocker"})
        requirements.append(item)
    resource_map = {
        "project.create":("POST /api/v1/projects","/"),
        "project.list":("GET /api/v1/projects","/"),
        "project.open":("GET /api/v1/projects/{project_id}","overview"),
        "project.validate":("GET /api/v1/projects/{project_id}/validation","overview via project state"),
        "domain-pack.discover":("GET /api/v1/domain-packs","/"),
        "job.get":("GET /api/v1/jobs/{job_id}","jobs via project state"),
        "source.register":("POST /api/v1/projects/{project_id}/sources","sources"),
        "source.inspect":("GET /api/v1/projects/{project_id}/sources/{source_id}","sources"),
        "ingestion.plan":("POST /api/v1/projects/{project_id}/ingestion/plans","sources"),
        "ingestion.run":("POST /api/v1/projects/{project_id}/ingestion/runs","sources"),
        "ingestion.inspect":("GET /api/v1/projects/{project_id}/ingestion/runs/{run_id}","sources"),
        "ingestion.trace":("GET /api/v1/projects/{project_id}/evidence?run_id=...&item_id=...","sources"),
        "modeling.scope":("POST /api/v1/projects/{project_id}/modeling/scopes","modeling"),
        "modeling.scope.approve":("POST /api/v1/projects/{project_id}/modeling/scope-approvals","modeling"),
        "modeling.proposal":("POST /api/v1/projects/{project_id}/modeling/proposals","modeling"),
        "review.action":("POST /api/v1/projects/{project_id}/reviews/actions","modeling"),
        "review.replay":("GET /api/v1/projects/{project_id}/reviews/{review_id}","modeling"),
        "review.finalize":("POST /api/v1/projects/{project_id}/reviews/finalizations","modeling"),
        "compile.plan":("POST /api/v1/projects/{project_id}/compilations/plans","releases"),
        "compile.build":("POST /api/v1/projects/{project_id}/compilations/builds","releases"),
        "registry.import":("POST /api/v1/projects/{project_id}/lifecycle/imports","releases"),
        "release.review":("POST /api/v1/projects/{project_id}/lifecycle/release-reviews","releases"),
        "release.publish":("POST /api/v1/projects/{project_id}/lifecycle/releases","releases"),
        "oms.metadata":("GET /api/v1/projects/{project_id}/metadata","releases"),
        "ods.query":("POST /api/v1/projects/{project_id}/objects/query","releases"),
    }
    limitations = {
        "modeling.scope.approve":["explicit approval revision CAS UX not completed"],
        "modeling.candidate":["manual/recorded Provider application adapters not connected"],
        "modeling.proposal":["manual/recorded Provider application adapters not connected"],
        "review.action":["modify-and-revalidate, conflict-resolution and evidence-request completion UI absent"],
        "compile.plan":["only SELECT/minimum-row/required-binding Oracle form is connected"],
        "release.publish":["only initial lineage service path verified; successor governance remains open"],
        "oms.metadata":["explicit Release selector and complete OMS views not implemented"],
        "ods.query":["only bounded class/instance primitives connected; full query timeout and trace UI not verified"],
    }
    for item in requirements:
        name = item["requirement_id"]
        if name in resource_map:
            item["api"], item["ui"] = resource_map[name]
        if name in {"modeling.cq","modeling.baseline","modeling.alignment"}:
            item.update(maps_to="modeling.prepare", api="POST /api/v1/projects/{project_id}/modeling/preparations", ui="modeling")
        if name == "modeling.candidate":
            item["maps_to"] = "modeling.proposal"
        item["missing"].extend(limitations.get(name, []))
        if name in limitations:
            item["status"] = "PARTIAL"
    additions = {
        "G0.baseline": "Fixed source, clean entry, ancestors, P8 protected tree and domain/schema byte audit",
        "G1.upload": "Bounded authenticated stream and Blob/SourceAsset/SourceBatch, cleanup and downloads",
        "G1.evidence": "Verified KG-IR, locators and Source Blob trace with project authorization",
        "G1.fencing": "Core CAS, revocation, two workers, crash/restart and idempotency recovery",
        "G2.dependencies": "Scope/CQ/baseline/terminology/alignment/input/provider/prevalidation/confirmation",
        "G2.review": "Server identities, roles, quorum, revisions and review action replay",
        "G2.validation": "Real reasoner, SHACL, explicit CQ oracle and provenance closure",
        "G3.lifecycle": "Feedback/change/consumer/diff/impact/regression/release/environment review and historical rollback",
        "G3.queries": "Version-bound local OMS/ODS, typed literals, paging, timeouts and safe query grammar",
        "G4.sessions": "Opaque HttpOnly sessions, CSRF, origin, expiration, revoke, logout and cache isolation",
        "G4.workbench": "One Chinese React/TypeScript/Vite workbench with actual forms, graph/table and API",
        "G4.domains": "Minimal/MNP/Forestry full graded workflows and arbitrary fourth pack",
        "G4.forestry": "Synthetic EXPERIMENTAL 0.2.0 tree/inspection/site assets and negative cases",
        "G4.browser": "Actual browser scenarios A-E, artifact IDs, screenshots, keyboard/a11y and performance",
        "G5.retirement": "Actual caller-led old code/UI/CLI/docs/script retirement after G1-G4",
        "G5.contracts": "115 versioned schema bytes, minimal/mnp and 84 MNP asset preservation",
        "G5.quality": "Capability test migration ledger, unique test sets and capability CI",
        "G5.docs": "Current product docs, operating commands, research implementation/evidence limits",
        "G6.distribution": "Wheel/sdist/static bundle with digests, clean install/startup/recovery on Windows and POSIX",
        "G6.freeze": "Clean fixed commit, complete pytest/browser collection, full command receipts and delivery consistency",
        "G6.delivery": "Normal target push, final decision and no success tag until required gates pass",
    }
    for name, source in additions.items():
        requirements.append(previous.get(name, {"requirement_id": name, "source_requirement": source,
                                               "implementation": [], "missing": [source], "core_required": True,
                                               "cli": None, "api": None, "sdk": None, "ui": None,
                                               "positive_tests": [], "negative_tests": [], "status": "OPEN",
                                               "blocker": None, "commits": []}))
    document = {"source_commit": SOURCE, "target_branch": "codex/toolchain-final-consolidation-p09",
                                  "historical_audit": {"status": "PASS", "file_count": count, "tree_digest": digest.hexdigest(),
                                                       "method": "git archive of fixed P8, LF-normalized source bytes", "ancestor_heads": heads},
                                  "original_operation_count": len(baseline["operations"]), "requirements": requirements}
    if args.check:
        if prior != document:
            raise SystemExit("Requirement ledger is stale")
    else:
        atomic_write_json(ledger_path, document)
    print(json.dumps({"historical_audit": "PASS", "baseline_operations_retained": len(baseline["operations"])}))


if __name__ == "__main__":
    main()
