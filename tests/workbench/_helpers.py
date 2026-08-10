from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.workbench.binding import WorkbenchBinding


PUBLICATION_HASH = "0e43e22adccec950dc6b638ffec5c3fdc2f0f43911704f9648e6171ae35161d3"
PUBLICATION_ID = "urn:kg-mnp:e2e-publication:" + PUBLICATION_HASH
REPOSITORY_ID = "kg-mnp-8e7873f07736e86f7d70"
REPOSITORY_HASH = "59a1ea58c20a43e4718cfa3dc7a5253bbe44b704aba3a9e4b47b302b70c639d4"
ENTITY = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/2993a1403cabddd34da97cacad8c5aa55103903ab9d3a0d831bd9f989f2fc029"
TERM = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#APIResponse"
ONTOLOGY_VERSION = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/1.0.0/mnp-evidence-time"


def iri(value: str) -> dict[str, Any]:
    return {"term_type": "IRI", "iri": value}


def literal(
    value: str,
    datatype: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    return {
        "term_type": "LITERAL",
        "lexical_form": value,
        "datatype_iri": datatype,
        "language": language,
    }


def row(**values: dict[str, Any]) -> dict[str, Any]:
    return {
        "bindings": [
            {"variable": variable, "term": term}
            for variable, term in values.items()
        ]
    }


def traceability(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "queried_resource": copy.deepcopy(parameters),
        "publication": {
            "publication_id": PUBLICATION_ID,
            "publication_semantic_hash": PUBLICATION_HASH,
        },
        "compilation": {"compilation_id": "urn:kg-mnp:compilation:test"},
        "graphdb": {
            "repository_id": REPOSITORY_ID,
            "graph_iris": ["urn:kg-mnp:graph:fixture"],
        },
        "business_facts": [],
        "modeling": [],
        "review": [],
        "evidence": [],
        "source": [],
    }


def query_result(
    query_id: str,
    parameters: dict[str, Any],
    variables: list[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "query_id": query_id,
        "query_version": "1.0.0",
        "publication_id": PUBLICATION_ID,
        "publication_semantic_hash": PUBLICATION_HASH,
        "repository_id": REPOSITORY_ID,
        "parameters": copy.deepcopy(parameters),
        "variables": variables,
        "results": copy.deepcopy(rows),
        "traceability": traceability(parameters),
        "result_count": len(rows),
        "truncated": False,
        "result_semantic_hash": "a" * 64,
        "runtime_metadata": {
            "duration_ms": 1.0,
            "served_at": "2026-08-10T00:00:00Z",
        },
    }


def health() -> dict[str, Any]:
    return {
        "status": "APPLICATION_READY",
        "read_only": True,
        "publication_id": PUBLICATION_ID,
        "publication_semantic_hash": PUBLICATION_HASH,
        "repository_id": REPOSITORY_ID,
        "expected_graphdb_semantic_hash": REPOSITORY_HASH,
        "live_graphdb_semantic_hash": REPOSITORY_HASH,
        "repository_semantic_identity_verified": True,
        "health": {"healthy": True, "repository_count": 1},
        "publication_authority_reconstruction": {
            "status": "PASS",
            "scenario": "full-confirmation",
            "publication_id": PUBLICATION_ID,
            "deterministic_reconstruction_match": True,
        },
    }


def write_phase01_artifact(directory: Path) -> Path:
    registry = QueryRegistry.load().manifest()
    authority = {
        "status": "PASS",
        "scenario": "full-confirmation",
        "publication_id": PUBLICATION_ID,
    }
    attestation = {
        "contract_version": "1.0",
        "expected_graphdb_semantic_hash": REPOSITORY_HASH,
        "golden_query_count": 12,
        "golden_query_passed": 12,
        "http_runtime": {
            "bind_host": "127.0.0.1",
            "golden_http_status": "PASS",
            "read_only": True,
        },
        "live_graphdb_semantic_hash_after": REPOSITORY_HASH,
        "live_graphdb_semantic_hash_before": REPOSITORY_HASH,
        "live_repository_tamper_attack_blocked": 3,
        "live_repository_tamper_attack_count": 3,
        "mutation_attack_blocked": 15,
        "mutation_attack_count": 15,
        "publication_authority_reconstruction": authority,
        "publication_id": PUBLICATION_ID,
        "publication_semantic_hash": PUBLICATION_HASH,
        "query_registry_hash": registry["query_registry_hash"],
        "repository_id": REPOSITORY_ID,
        "repository_semantic_identity_verified": True,
        "repository_unchanged": True,
        "result_determinism": "PASS",
        "status": "APPLICATION_READONLY_VERIFIED",
        "traceability_checks": {
            "evidence": "PASS",
            "fact_level": "PASS",
            "publication_lineage": "PASS",
            "review": "PASS",
            "source": "PASS",
        },
    }
    documents = {
        "application-attestation.json": attestation,
        "query-registry-manifest.json": registry,
        "golden-query-summary.json": {
            "contract_version": "1.0",
            "publication_id": PUBLICATION_ID,
            "query_registry_hash": registry["query_registry_hash"],
            "golden_query_count": 12,
            "golden_query_passed": 12,
            "status": "PASS",
        },
        "security-summary.json": {
            "contract_version": "1.0",
            "publication_id": PUBLICATION_ID,
            "repository_id": REPOSITORY_ID,
            "mutation_attack_count": 15,
            "mutation_attack_blocked": 15,
            "live_repository_tamper_attack_count": 3,
            "live_repository_tamper_attack_blocked": 3,
            "status": "PASS",
        },
        "graphdb-before-after.json": {
            "contract_version": "1.0",
            "publication_id": PUBLICATION_ID,
            "repository_id": REPOSITORY_ID,
            "expected_graphdb_semantic_hash": REPOSITORY_HASH,
            "live_graphdb_semantic_hash_before": REPOSITORY_HASH,
            "live_graphdb_semantic_hash_after": REPOSITORY_HASH,
            "publication_authority_reconstruction": authority,
            "repository_semantic_identity_verified": True,
            "repository_unchanged": True,
        },
    }
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in documents.items():
        (directory / name).write_bytes(canonical_json_bytes(payload) + b"\n")
    return directory


class FakeRelay:
    def __init__(self, binding: WorkbenchBinding, payload: str = "ACTIVE"):
        self.binding = binding
        self.payload = payload

    def health(self) -> dict[str, Any]:
        return health()

    def query(self, path: str, parameters: dict[str, Any]) -> dict[str, Any]:
        result_parameters = copy.deepcopy(parameters)
        if path in {"/api/v1/fact", "/api/v1/fact/provenance"}:
            object_type = result_parameters.pop("object_type")
            object_value = result_parameters.pop("object_value")
            if object_type == "IRI":
                object_term = {"term_type": "IRI", "value": object_value}
            else:
                object_term = {
                    "term_type": "LITERAL",
                    "value": object_value,
                    "datatype_iri": result_parameters.pop("datatype_iri", None),
                    "language": result_parameters.pop("language", None),
                }
            result_parameters["object"] = object_term
        mapping = {
            "/api/v1/ontology/classes": (
                "ontology.classes",
                ["graph", "term", "label"],
                [
                    row(
                        graph=iri("urn:kg-mnp:graph:tbox:test"),
                        term=iri(TERM),
                        label=literal(self.payload, language="en"),
                    )
                ],
            ),
            "/api/v1/ontology/properties": (
                "ontology.properties",
                ["graph", "term", "termType"],
                [
                    row(
                        graph=iri("urn:kg-mnp:graph:tbox:test"),
                        term=iri("urn:kg-mnp:property:test"),
                        termType=iri("http://www.w3.org/2002/07/owl#DatatypeProperty"),
                    )
                ],
            ),
            "/api/v1/ontology/term": (
                "ontology.term",
                ["graph", "term", "ontologyVersion"],
                [
                    row(
                        graph=iri("urn:kg-mnp:graph:tbox:test"),
                        term=iri(TERM),
                        ontologyVersion=iri(ONTOLOGY_VERSION),
                    )
                ],
            ),
            "/api/v1/entity": (
                "business.entity",
                ["graph", "direction", "subject", "predicate", "object"],
                [
                    row(
                        graph=iri("urn:kg-mnp:graph:fixture"),
                        direction=literal("OUTGOING"),
                        subject=iri(ENTITY),
                        predicate=iri("urn:kg-mnp:predicate:test"),
                        object=literal(self.payload, datatype="urn:datatype:test"),
                    )
                ],
            ),
            "/api/v1/fact": (
                "business.fact",
                ["graph", "subject", "predicate", "object"],
                [
                    row(
                        graph=iri("urn:kg-mnp:graph:fixture"),
                        subject=iri(ENTITY),
                        predicate=iri("urn:kg-mnp:predicate:test"),
                        object=literal(self.payload, datatype="urn:datatype:test"),
                    )
                ],
            ),
            "/api/v1/fact/provenance": (
                "provenance.fact",
                [
                    "businessGraph",
                    "subject",
                    "predicate",
                    "object",
                    "candidateId",
                    "decisionId",
                    "outcome",
                    "evidenceRef",
                    "sourceRef",
                ],
                [
                    row(
                        businessGraph=iri("urn:kg-mnp:graph:fixture"),
                        subject=iri(ENTITY),
                        predicate=iri("urn:kg-mnp:predicate:test"),
                        object=literal(self.payload, datatype="urn:datatype:test"),
                        candidateId=iri("urn:kg-mnp:candidate:test"),
                        decisionId=iri("urn:kg-mnp:decision:test"),
                        outcome=literal("CONFIRM"),
                        evidenceRef=iri("urn:kg-mnp:evidence:test"),
                        sourceRef=iri("urn:kg-mnp:source:test"),
                    )
                ],
            ),
            "/api/v1/review-trace": (
                "review.trace",
                ["subject", "decisionId", "outcome"],
                [
                    row(
                        subject=iri("urn:kg-mnp:candidate:test"),
                        decisionId=iri("urn:kg-mnp:decision:test"),
                        outcome=literal("REJECT"),
                    )
                ],
            ),
            "/api/v1/source-trace": (
                "source.trace",
                ["sourceRef"],
                [row(sourceRef=iri("urn:kg-mnp:source:test"))],
            ),
            "/api/v1/evidence-trace": (
                "evidence.trace",
                ["evidenceRef"],
                [row(evidenceRef=iri("urn:kg-mnp:evidence:test"))],
            ),
            "/api/v1/trace": (
                "trace.resource",
                ["resource"],
                [row(resource=iri("urn:kg-mnp:resource:test"))],
            ),
        }
        query_id, variables, rows = mapping[path]
        result = query_result(query_id, result_parameters, variables, rows)
        if query_id == "provenance.fact":
            result["traceability"].update(
                {
                    "business_facts": [
                        {
                            "subject": iri(ENTITY),
                            "predicate": iri("urn:kg-mnp:predicate:test"),
                            "object": literal(
                                self.payload,
                                datatype="urn:datatype:test",
                            ),
                        }
                    ],
                    "modeling": [
                        {
                            "assertion_id": "urn:kg-mnp:assertion:test",
                            "candidate_id": "urn:kg-mnp:candidate:test",
                            "effective_candidate_id": "urn:kg-mnp:candidate:test",
                        }
                    ],
                    "review": [
                        {
                            "decision_id": "urn:kg-mnp:decision:test",
                            "outcome": "CONFIRM",
                            "reviewer_id": "urn:kg-mnp:reviewer:test",
                            "decided_at": "2026-08-10T00:00:00Z",
                        }
                    ],
                    "evidence": [{"evidence_ref": "urn:kg-mnp:evidence:test"}],
                    "source": [{"source_ref": "urn:kg-mnp:source:test"}],
                }
            )
        return result
