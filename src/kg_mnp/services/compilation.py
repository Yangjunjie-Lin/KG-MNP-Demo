"""Verified-confirmation compiler adapter; all validation is run by the kernel."""
from __future__ import annotations

from pathlib import Path

from kg_mnp.contracts.canonical import file_sha256
from kg_mnp.contracts.document_io import read_document
from kg_mnp.domain_packs.registry import DomainPackRegistry
from kg_mnp.semantic_kernel.baseline import load_baseline_closure
from kg_mnp.semantic_kernel.compiler import SemanticCompiler
from kg_mnp.semantic_kernel.errors import SemanticKernelError
from kg_mnp.semantic_kernel.identifiers import package_storage_key
from kg_mnp.semantic_kernel.packaging.archive import export_kgop
from kg_mnp.semantic_kernel.packaging.verifier import verify_package
from kg_mnp.semantic_kernel.validators.competency_questions import build_cq_test_plan
from kg_mnp.workspace.locking import load_project_lock

from .errors import ServiceBoundaryError

OPERATIONS = frozenset({"compile.plan", "compile.build", "compile.validate", "compile.reproduce", "package.verify", "package.export"})


def package_path(project, package_id):
    try:
        path = Path(project.root) / "artifacts" / "packages" / package_storage_key(package_id)
        manifest = read_document(path / "ontology-package.json", max_bytes=16 * 1024 * 1024)
        if manifest["package_id"] != package_id:
            raise ValueError("package ID mismatch")
        verify_package(path)
        return path
    except (OSError, ValueError, KeyError, SemanticKernelError) as exc:
        raise ServiceBoundaryError("PACKAGE_INVALID", "package is absent or invalid in this project", status_code=409) from exc


def execute(app, project, request, principal):
    name, params = request.operation_id, request.parameters
    try:
        if name in {"package.verify", "compile.validate", "package.export"}:
            path = package_path(project, params["package_id"])
            if name == "package.export":
                destination = Path(project.root) / "artifacts" / "builds" / "exports"
                destination.mkdir(parents=True, exist_ok=True)
                archive = destination / (package_storage_key(params["package_id"]) + ".kgop")
                export_kgop(path, archive)
                return {"package_id": params["package_id"], "sha256": file_sha256(archive), "size_bytes": archive.stat().st_size}
            return {"package_id": params["package_id"], "status": "VERIFIED", "validation": read_document(path / "validation/ontology-package-validation-report.json")}
        compiler = SemanticCompiler(project.root, domain_packs_root=DomainPackRegistry(app.configuration.domain_packs_root).root,
                                    reasoner_jar=app.configuration.reasoner_jar)
        if name == "compile.plan":
            confirmed = compiler.confirmed(params["confirmed_package_id"])
            question_set = compiler._resolver().resolve(confirmed["competency_question_set_id"]).document
            if {q["question_id"] for q in question_set["questions"]} != {o["question_id"] for o in params["oracles"]}:
                raise ServiceBoundaryError("CQ_ORACLE_REQUIRED", "every confirmed CQ requires an explicit oracle", status_code=422)
            baseline = load_baseline_closure(load_project_lock(Path(project.root)).document,
                                             domain_packs_root=compiler.domain_packs_root)
            tests = []
            questions = {q["question_id"]: q for q in question_set["questions"]}
            for oracle in params["oracles"]:
                if oracle["query_asset_id"] not in baseline.query_assets:
                    raise ServiceBoundaryError("CQ_QUERY_UNAVAILABLE", "query must be a locked local Domain Pack asset", status_code=422)
                tests.append({"question_id": oracle["question_id"], "requirement": "REQUIRED", "query_artifact_ref": oracle["query_asset_id"],
                    "query_type": "SELECT", "target_graph_roles": ["abox"], "expected_answer_shape": questions[oracle["question_id"]]["expected_answer_shape"],
                    "assertions": [
                        {"assertion_type": "MIN_ROW_COUNT", "integer_value": oracle["min_rows"], "boolean_value": None, "string_values": [], "semantic_hash": None},
                        {"assertion_type": "REQUIRED_BINDINGS", "integer_value": None, "boolean_value": None, "string_values": oracle["required_bindings"], "semantic_hash": None}],
                    "resource_limits": [{"name": "max_query_characters", "value": 100000}, {"name": "max_query_results", "value": 100000},
                                        {"name": "max_query_seconds", "value": 30}, {"name": "max_query_path_depth", "value": 8}]})
            cq_plan = build_cq_test_plan(tests, query_loader=lambda ref: baseline.query_assets[ref])
            plan, attestation = compiler.create_plan(package_id=params["confirmed_package_id"], package_name=params["package_name"],
                package_version=params["package_version"], ontology_iri=params["ontology_iri"], version_iri=params["version_iri"], cq_test_plan=cq_plan)
            return {"plan": plan, "attestation": attestation}
        if name == "compile.reproduce":
            return compiler.reproduce(params["plan_id"])
        result = compiler.build(params["plan_id"])
        path = result.package_directory
        reports = {p.name: read_document(p, max_bytes=16 * 1024 * 1024) for p in (path / "validation").glob("*report.json")}
        return {"package_id": result.package_id, "build_id": result.build_id,
                "manifest": read_document(path / "ontology-package.json", max_bytes=16 * 1024 * 1024), "reports": reports}
    except SemanticKernelError as exc:
        raise ServiceBoundaryError(exc.code, "semantic compiler rejected the input or validation failed", status_code=422) from exc
    except (OSError, ValueError) as exc:
        raise ServiceBoundaryError("COMPILATION_BLOCKED", "compiler input, dependency or package is unavailable", status_code=422) from exc
