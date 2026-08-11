"""Load diagnostics exclusively from independently verified local authorities."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rdflib import RDF, Graph, Literal, URIRef

from kg_mnp_demo.application.artifact_verifier import (
    verify_application_phase01_artifact,
)
from kg_mnp_demo.application.publication_binding import PublicationBinding
from kg_mnp_demo.compilation.abox_compiler import compile_abox
from kg_mnp_demo.workbench.artifact_verifier import (
    verify_application_phase02_artifact,
)

from .authority_binding import AuthorityBindings
from .contracts import strict_json_file
from .engine import AuthoritySnapshot
from .errors import DiagnosticError, DiagnosticErrorCode
from .policy import diagnostic_policy_hash
from .requirement_index import reconstruct_requirements_from_shacl


def _verified_artifact_document(
    directory: Path,
    filename: str,
    verifier,
    expected_status: str,
) -> tuple[dict[str, Any], str]:
    root = Path(directory)
    try:
        result = verifier(root)
        path = root / filename
        raw = path.read_bytes()
        document = strict_json_file(path)
    except Exception as exc:
        raise DiagnosticError(DiagnosticErrorCode.AUTHORITY_MISMATCH) from exc
    if result.get("status") != expected_status or document.get("status") != expected_status:
        raise DiagnosticError(DiagnosticErrorCode.AUTHORITY_MISMATCH)
    return document, hashlib.sha256(raw).hexdigest()


def load_verified_authority_bindings(
    *,
    publication_manifest: Mapping[str, Any],
    phase01_artifact_directory: Path,
    phase02_artifact_directory: Path,
) -> AuthorityBindings:
    phase01, phase01_hash = _verified_artifact_document(
        phase01_artifact_directory,
        "application-attestation.json",
        verify_application_phase01_artifact,
        "APPLICATION_READONLY_VERIFIED",
    )
    phase02, phase02_hash = _verified_artifact_document(
        phase02_artifact_directory,
        "application-phase02-attestation.json",
        verify_application_phase02_artifact,
        "APPLICATION_WORKBENCH_VERIFIED",
    )
    publication_id = publication_manifest.get("publication_id")
    publication_hash = publication_manifest.get("publication_semantic_hash")
    repository_hash = phase01.get("expected_graphdb_semantic_hash")
    expected_pairs = (
        (phase01.get("publication_id"), publication_id),
        (phase01.get("publication_semantic_hash"), publication_hash),
        (phase02.get("publication_id"), publication_id),
        (phase02.get("publication_semantic_hash"), publication_hash),
        (phase02.get("phase01_attestation_hash"), phase01_hash),
        (phase02.get("repository_hash_expected"), repository_hash),
        (phase02.get("query_registry_hash"), phase01.get("query_registry_hash")),
    )
    if any(left != right for left, right in expected_pairs):
        raise DiagnosticError(
            DiagnosticErrorCode.AUTHORITY_MISMATCH,
            "verified application lineage mismatch",
        )
    return AuthorityBindings(
        publication_id=str(publication_id),
        publication_semantic_hash=str(publication_hash),
        phase01_attestation_hash=phase01_hash,
        phase02_attestation_hash=phase02_hash,
        query_registry_hash=str(phase01["query_registry_hash"]),
        repository_semantic_hash=str(repository_hash),
        diagnostic_policy_hash=diagnostic_policy_hash(),
    )


def _rdf_value(value: Any) -> dict[str, Any]:
    if isinstance(value, URIRef):
        return {"term_type": "IRI", "iri": str(value)}
    if isinstance(value, Literal):
        return {
            "term_type": "LITERAL",
            "lexical_form": str(value),
            "datatype_iri": str(value.datatype) if value.datatype else None,
            "language": value.language,
        }
    raise ValueError("unsupported asserted RDF term")


def _facts_from_verified_compilation(
    confirmed: Mapping[str, Any],
    proposal: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> tuple[Graph, list[dict[str, Any]]]:
    graph, assertions = compile_abox(confirmed, proposal, baseline)
    facts = []
    for assertion in assertions:
        subject, predicate, value = assertion.triple
        content = assertion.semantic_content
        facts.append(
            {
                "focus_node": str(subject),
                "path": str(predicate),
                "value": _rdf_value(value),
                "assertion_ref": assertion.confirmed_item_id,
                "status": "CONFIRMED",
                "evidence_refs": content.get("business_fact_evidence_refs", []),
                "source_refs": content.get("source_paths", []),
            }
        )
    return graph, facts


def _proposal_candidates(proposal: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for field in ("candidate_entities", "candidate_assertions", "schema_delta_candidates"):
        for candidate in proposal.get(field, []):
            if isinstance(candidate, Mapping) and candidate.get("candidate_id"):
                result[str(candidate["candidate_id"])] = dict(candidate)
    return result


def _resolve_reference(value: Any, candidates: Mapping[str, Mapping[str, Any]]) -> Any:
    candidate = candidates.get(str(value))
    if candidate is not None and candidate.get("proposed_iri"):
        return candidate["proposed_iri"]
    return value


def _candidate_record(
    candidate: Mapping[str, Any],
    decision: Mapping[str, Any],
    candidates: Mapping[str, Mapping[str, Any]],
    *,
    publication_id: str,
) -> dict[str, Any]:
    kind = str(candidate.get("candidate_kind", "ENTITY"))
    if kind == "ENTITY":
        focus = candidate.get("proposed_iri")
        path = str(RDF.type)
        value = candidate.get("class_iri")
    else:
        focus = _resolve_reference(candidate.get("subject_ref"), candidates)
        path = candidate.get("predicate_iri") or str(RDF.type)
        value = _resolve_reference(
            candidate.get("object", candidate.get("class_iri")), candidates
        )
    decision_id = str(decision["decision_id"])
    return {
        "focus_node": str(focus),
        "path": str(path),
        "value": value,
        "outcome": str(decision["decision"]),
        "candidate_ref": str(candidate["candidate_id"]),
        "review_decision_ref": decision_id,
        "evidence_refs": decision.get("evidence_refs", []),
        "source_refs": candidate.get("source_paths", []),
        "authority_basis": [
            {
                "requirement_type": "FROZEN_REVIEW_DECISION",
                "authority_iri": decision_id,
                "shape_iri": None,
                "constraint_iri": None,
                "module": "review-audit",
                "publication_id": publication_id,
            }
        ],
    }


def load_verified_authority_snapshot(
    *,
    publication_package_directory: Path,
    publication_attestation_path: Path,
    publication_scenario: str,
    phase01_artifact_directory: Path,
    phase02_artifact_directory: Path,
) -> AuthoritySnapshot:
    """Validate all authorities, then reconstruct facts and formal requirements."""

    try:
        publication = PublicationBinding.verify(
            publication_package_directory,
            publication_attestation_path,
            publication_scenario=publication_scenario,
        )
        root = publication.package_directory
        proposal = strict_json_file(root / "source" / "modeling-proposal.json")
        confirmed = strict_json_file(root / "source" / "confirmed-modeling-package.json")
        decision_log = strict_json_file(root / "source" / "review-decision-log.json")
        baseline = strict_json_file(root / "source" / "ontology-baseline.json")
        bindings = load_verified_authority_bindings(
            publication_manifest=publication.manifest,
            phase01_artifact_directory=phase01_artifact_directory,
            phase02_artifact_directory=phase02_artifact_directory,
        )
        data_graph, facts = _facts_from_verified_compilation(
            confirmed,
            proposal,
            baseline,
        )
        shape_path = (
            Path(__file__).resolve().parents[3]
            / "shapes"
            / "foundation-instance-shapes.ttl"
        )
        profile_record = next(
            record
            for record in publication.compilation_manifest["artifact_manifest"]
            if record.get("relative_path")
            == "shacl/profiles/foundation-instance-shapes.ttl"
        )
        if hashlib.sha256(shape_path.read_bytes()).hexdigest() != profile_record.get(
            "byte_sha256"
        ):
            raise DiagnosticError(
                DiagnosticErrorCode.AUTHORITY_MISMATCH,
                "local formal constraint profile does not match publication",
            )
        shapes = Graph()
        shapes.parse(shape_path, format="turtle")
        requirement_index = reconstruct_requirements_from_shacl(
            shapes,
            data_graph,
            publication_id=bindings.publication_id,
            module="foundation-instance-shapes",
        )
        candidates = _proposal_candidates(proposal)
        history = [
            _candidate_record(
                candidates[str(decision["candidate_id"])],
                decision,
                candidates,
                publication_id=bindings.publication_id,
            )
            for decision in decision_log.get("decisions", [])
            if decision.get("candidate_id") in candidates
        ]
    except DiagnosticError:
        raise
    except Exception as exc:
        raise DiagnosticError(DiagnosticErrorCode.AUTHORITY_MISMATCH) from exc
    return AuthoritySnapshot(
        authority_bindings=bindings,
        requirements=tuple(
            {
                **requirement.authority_basis(),
                "focus_node": requirement.focus_node,
                "path": requirement.path,
                "min_count": requirement.min_count,
                "max_count": requirement.max_count,
            }
            for requirement in requirement_index
        ),
        facts=tuple(facts),
        constraint_results=(),
        candidates=tuple(history),
        conflict_rules=(),
    )
