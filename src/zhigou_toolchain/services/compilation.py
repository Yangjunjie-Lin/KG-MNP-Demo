"""Verified-confirmation compiler adapter; all validation is run by the kernel."""
from __future__ import annotations

from pathlib import Path

from zhigou_toolchain.contracts.canonical import file_sha256
from zhigou_toolchain.contracts.document_io import read_document
from zhigou_toolchain.contracts.errors import ContractError
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry
from zhigou_toolchain.semantic_kernel.baseline import load_baseline_closure
from zhigou_toolchain.semantic_kernel.compiler import SemanticCompiler
from zhigou_toolchain.semantic_kernel.errors import SemanticKernelError
from zhigou_toolchain.semantic_kernel.identifiers import package_storage_key
from zhigou_toolchain.semantic_kernel.packaging.archive import export_kgop
from zhigou_toolchain.semantic_kernel.packaging.verifier import verify_package
from zhigou_toolchain.semantic_kernel.validators.competency_questions import (
    build_cq_test_plan,
)
from zhigou_toolchain.workspace.locking import load_project_lock

from .errors import ServiceBoundaryError

OPERATIONS = frozenset({"compile.plan", "compile.plan.exact", "compile.build", "compile.validate", "compile.reproduce", "package.verify", "package.export"})


def read_export_snapshot(service, principal, project_id: str, job_id: str) -> bytes:
    """Download one explicitly selected, previously verified export snapshot.

    This is not the mutable package reader and does not cache its verdict.
    The fenced export already ran export_kgop; verify its committed generation
    and exact archive bytes again, with current authorization at both ends.
    """
    from zhigou_toolchain.contracts.canonical import bytes_sha256

    from .authorization_policy import authorize
    from .execution import committed_result
    from .models import OperationRequest
    from .projects import get_project, load_catalog, require_access

    principal = service._current(principal)
    request = OperationRequest("package.verify", project_id, {"package_id": "export-snapshot"})
    def authorized(current):
        authorize(current, service.catalog["package.verify"], request)
        if not current.can("package:export"):
            raise ServiceBoundaryError("FORBIDDEN", "package:export required", status_code=403)
        require_access(current, get_project(service.root, project_id))
    authorized(principal)
    job = service._job(job_id, principal)
    if job.project_id != project_id or job.operation_id != "package.export":
        raise ServiceBoundaryError("EXPORT_SCOPE_INVALID", "export task belongs to another resource", status_code=404)
    result = committed_result(service, job)
    if result is None:
        raise ServiceBoundaryError("EXPORT_NOT_READY", "export has no verified commit", status_code=409)
    record = load_catalog(service.root).get("commits", {}).get(job_id)
    if not record or record["result"] != result:
        raise ServiceBoundaryError("EXPORT_INTEGRITY_FAILED", "export commit changed", status_code=409)
    try:
        generation = Path(record["root"]).resolve(strict=True)
        if not generation.is_relative_to((service.root / "projects").resolve()):
            raise ValueError("export outside project storage")
        archive = generation / "artifacts" / "builds" / "exports" / (package_storage_key(result["package_id"]) + ".kgop")
        if archive.is_symlink() or not archive.resolve(strict=True).is_relative_to(generation):
            raise ValueError("linked export")
        content = archive.read_bytes()
        if len(content) != result["size_bytes"] or bytes_sha256(content) != result["sha256"]:
            raise ValueError("export bytes changed")
    except (OSError, ValueError, KeyError) as exc:
        raise ServiceBoundaryError("EXPORT_INTEGRITY_FAILED", "export snapshot bytes failed verification", status_code=409) from exc
    authorized(service._current(principal))
    return content


def read_archive(service, principal, project_id: str, package_id: str) -> bytes:
    """One explicit project snapshot and one byte-bound validation per download."""
    from zhigou_toolchain.semantic_kernel.packaging.archive import archive_bytes

    from .authorization_policy import authorize
    from .models import OperationRequest
    from .projects import get_project, require_access
    from .requests import validate_parameters

    request = OperationRequest("package.verify", project_id, {"package_id": package_id})
    operation = service.catalog["package.verify"]
    principal = service._current(principal)
    authorize(principal, operation, request)
    if not principal.can("package:export"):
        raise ServiceBoundaryError("FORBIDDEN", "package:export required", status_code=403)
    validate_parameters(request)
    project = get_project(service.root, project_id)
    require_access(principal, project)
    try:
        # Location is not a cached verdict. archive_bytes verifies the exact
        # captured file set, including manifest, lock, source and RDF semantics.
        content = archive_bytes(package_location(project, package_id), expected_package_id=package_id)
        principal = service._current(principal)
        authorize(principal, operation, request)
        if not principal.can("package:export"):
            raise ServiceBoundaryError("FORBIDDEN", "package:export revoked", status_code=403)
        require_access(principal, get_project(service.root, project_id))
        service.audit.append(principal_id=principal.principal_id, operation_id="package.export", project_id=project_id,
            request_id=request.request_id, outcome="SUCCEEDED", details={"transport": "authorized-download"})
        return content
    except (SemanticKernelError, OSError, ValueError) as exc:
        raise ServiceBoundaryError("PACKAGE_INVALID", "package archive validation failed", status_code=409) from exc


def package_location(project, package_id):
    """Resolve project membership/identity; the consuming reader must verify bytes."""
    try:
        path = Path(project.root) / "artifacts" / "packages" / package_storage_key(package_id)
        manifest = read_document(path / "ontology-package.json", max_bytes=16 * 1024 * 1024)
        if manifest["package_id"] != package_id:
            raise ValueError("package ID mismatch")
        return path
    except (OSError, ValueError, KeyError, ContractError) as exc:
        raise ServiceBoundaryError("PACKAGE_INVALID", "package is absent or invalid in this project", status_code=409) from exc


def package_path(project, package_id):
    path = package_location(project, package_id)
    try:
        verify_package(path)
    except (OSError, ValueError, KeyError, ContractError) as exc:
        raise ServiceBoundaryError("PACKAGE_INVALID", "package is absent or invalid in this project", status_code=409) from exc
    return path


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
        if name in {"compile.plan", "compile.plan.exact"}:
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
                    "query_type": oracle["expected"]["query_type"] if name == "compile.plan.exact" else "SELECT", "target_graph_roles": ["abox"], "expected_answer_shape": questions[oracle["question_id"]]["expected_answer_shape"],
                    "assertions": [] if name == "compile.plan.exact" else [
                        {"assertion_type": "MIN_ROW_COUNT", "integer_value": oracle["min_rows"], "boolean_value": None, "string_values": [], "semantic_hash": None},
                        {"assertion_type": "REQUIRED_BINDINGS", "integer_value": None, "boolean_value": None, "string_values": oracle["required_bindings"], "semantic_hash": None}],
                    "resource_limits": [{"name": "max_query_characters", "value": 100000}, {"name": "max_query_results", "value": 100000},
                                        {"name": "max_query_seconds", "value": 30}, {"name": "max_query_path_depth", "value": 8}]})
                if name == "compile.plan.exact":
                    from zhigou_toolchain.modeling.five_stage.exact_answers import (
                        ExactAnswer,
                        assertions,
                    )
                    tests[-1]["assertions"] = assertions(ExactAnswer.model_validate(oracle["expected"]))
            cq_plan = build_cq_test_plan(tests, query_loader=lambda ref: baseline.query_assets[ref])
            plan, attestation = compiler.create_plan(package_id=params["confirmed_package_id"], package_name=params["package_name"],
                package_version=params["package_version"], ontology_iri=params["ontology_iri"], version_iri=params["version_iri"], cq_test_plan=cq_plan)
            return {"plan": plan, "attestation": attestation,
                    **({"independent_expected_answers": params["oracles"], "comparison_profile": "TYPED_EXACT_V1"} if name == "compile.plan.exact" else {})}
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
