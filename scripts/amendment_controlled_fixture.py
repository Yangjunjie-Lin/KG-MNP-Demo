"""TEST-ONLY full Stage04--08 Phase05 re-publication harness."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from rdflib import Graph, Literal, URIRef

from kg_mnp_demo.amendment.authority_binding import require_production_authority
from kg_mnp_demo.amendment.candidate_binding import bind_amendment_to_proposal
from kg_mnp_demo.amendment.errors import AmendmentError, AmendmentErrorCode
from kg_mnp_demo.amendment.fixture import ControlledAmendmentFixture
from kg_mnp_demo.amendment.intake import AmendmentIntakeManifest, ReplayGuard
from kg_mnp_demo.amendment.lineage import build_amendment_lineage
from kg_mnp_demo.amendment.republication import complete_reentry, prepare_reentry
from kg_mnp_demo.amendment.review_bridge import require_explicit_review
from kg_mnp_demo.amendment.scope import validate_amendment_scope
from kg_mnp_demo.amendment.validator import (
    validate_new_repository_identity,
    validate_no_direct_mutation,
)
from kg_mnp_demo.compilation.artifacts import write_artifact_set
from kg_mnp_demo.compilation.compiler import build_artifact_set
from kg_mnp_demo.compilation.policy import load_compiler_policy
from kg_mnp_demo.diagnostics.authority_binding import AuthorityBindings
from kg_mnp_demo.diagnostics.engine import AuthoritySnapshot, reconstruct_diagnostics
from kg_mnp_demo.diagnostics.policy import diagnostic_policy_hash
from kg_mnp_demo.graphdb.package_builder import build_graphdb_import_package
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash
from kg_mnp_demo.modeling.confirmation import build_confirmed_modeling_package
from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.package_validation import load_term_type_index
from kg_mnp_demo.modeling.proposal import generate_modeling_proposal
from kg_mnp_demo.modeling.review_log import (
    finalize_review_decision_log,
    init_review_decision_log,
    record_review_action,
)
from kg_mnp_demo.modeling.review_policy import load_default_review_policy
from kg_mnp_demo.modeling.semantic_validation import (
    validate_confirmed_modeling_package_semantics,
)
from kg_mnp_demo.publication.package_builder import (
    build_end_to_end_publication_package,
)

FIXTURE_REVIEWER = "urn:kg-mnp:reviewer:phase05-controlled-human"


def _record_all_human_decisions(
    cleaned: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    label: str,
    dependencies: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    review_policy = dependencies["review_policy"]
    term_types = dependencies["term_types"]
    log = init_review_decision_log(
        proposal,
        reviewer_id=FIXTURE_REVIEWER,
        display_name="Phase05 controlled human reviewer",
        role="CONTROLLED_TEST_REVIEWER",
        started_at="2026-08-16T00:00:00Z",
        session_label=f"phase05-{label}",
        review_policy=review_policy,
    )
    targets = [
        ("candidate_id", candidate["candidate_id"], "CONFIRM")
        for candidate in sorted(
            [
                *proposal.get("candidate_entities", []),
                *proposal.get("candidate_assertions", []),
            ],
            key=lambda item: item["candidate_id"],
        )
    ]
    targets.extend(
        ("issue_id", issue["issue_id"], "REJECT")
        for issue in sorted(
            proposal.get("issues", []), key=lambda item: item["issue_id"]
        )
    )
    for index, (kind, identifier, decision) in enumerate(targets, 1):
        action = {
            "contract_version": "1.0",
            "proposal_id": proposal["proposal_id"],
            "proposal_semantic_hash": proposal["proposal_semantic_hash"],
            "reviewer_id": FIXTURE_REVIEWER,
            "target": {kind: identifier},
            "decision": decision,
            "rationale": f"Explicit controlled human {decision} decision for {label}.",
            "decided_at": f"2026-08-16T00:{index:02d}:00Z",
            "evidence_refs": [f"phase05-controlled-review:{label}:{index:02d}"],
        }
        log = record_review_action(
            proposal,
            log,
            action,
            review_policy=review_policy,
            term_types=term_types,
        )
    log = finalize_review_decision_log(
        proposal,
        log,
        completed_at="2026-08-16T01:00:00Z",
        review_policy=review_policy,
        term_types=term_types,
        cleaned_partial_data=cleaned,
        ontology_baseline=dependencies["ontology_baseline"],
        mapping_rules=dependencies["mapping_rules"],
    )
    package = build_confirmed_modeling_package(
        cleaned,
        proposal,
        log,
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        review_policy,
        term_types=term_types,
    )
    validate_confirmed_modeling_package_semantics(
        package,
        proposal,
        log,
        cleaned_partial_data=cleaned,
        ontology_baseline=dependencies["ontology_baseline"],
        mapping_rules=dependencies["mapping_rules"],
        terminology_profile=dependencies["terminology_profile"],
        proposal_policy=dependencies["proposal_policy"],
        review_policy=review_policy,
        term_types=term_types,
        require_complete=True,
    )
    return log, package


def _review_outcome_probe(
    cleaned: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    prepared: Any,
    outcome: str,
    dependencies: Mapping[str, Any],
) -> bool:
    """Exercise REJECT/DEFER with the existing review engine and stop pre-publish."""

    log = init_review_decision_log(
        proposal,
        reviewer_id=FIXTURE_REVIEWER,
        display_name="Phase05 controlled human reviewer",
        role="CONTROLLED_TEST_REVIEWER",
        started_at="2026-08-16T02:00:00Z",
        session_label=f"phase05-{outcome.casefold()}-probe",
        review_policy=dependencies["review_policy"],
    )
    candidates = sorted(
        [
            *proposal.get("candidate_entities", []),
            *proposal.get("candidate_assertions", []),
        ],
        key=lambda item: item["candidate_id"],
    )
    first = candidates[0]["candidate_id"] if candidates else None
    targets = [
        (
            "candidate_id",
            candidate["candidate_id"],
            outcome if candidate["candidate_id"] == first else "CONFIRM",
        )
        for candidate in candidates
    ]
    targets.extend(
        ("issue_id", issue["issue_id"], "REJECT")
        for issue in proposal.get("issues", [])
    )
    for index, (kind, identifier, decision) in enumerate(targets, 1):
        log = record_review_action(
            proposal,
            log,
            {
                "contract_version": "1.0",
                "proposal_id": proposal["proposal_id"],
                "proposal_semantic_hash": proposal["proposal_semantic_hash"],
                "reviewer_id": FIXTURE_REVIEWER,
                "target": {kind: identifier},
                "decision": decision,
                "rationale": f"Controlled {outcome} probe.",
                "decided_at": f"2026-08-16T02:{index:02d}:00Z",
                "evidence_refs": [
                    f"phase05-controlled-{outcome.casefold()}:{index:02d}"
                ],
            },
            review_policy=dependencies["review_policy"],
            term_types=dependencies["term_types"],
        )
    finalized = finalize_review_decision_log(
        proposal,
        log,
        completed_at="2026-08-16T03:00:00Z",
        review_policy=dependencies["review_policy"],
        term_types=dependencies["term_types"],
        cleaned_partial_data=cleaned,
        ontology_baseline=dependencies["ontology_baseline"],
        mapping_rules=dependencies["mapping_rules"],
    )
    result = complete_reentry(
        prepared,
        decision_log=finalized,
        dependencies=dependencies,
        revised_cleaned_data=cleaned,
    )
    expected_status = {
        "REJECT": "REVIEW_REJECTED",
        "DEFER": "REVIEW_DEFERRED",
    }[outcome]
    return (
        result.status == expected_status
        and result.confirmed_package is None
        and result.compilation is None
        and result.publication is None
    )


def _record(manifest: Mapping[str, Any], relative_path: str) -> Mapping[str, Any]:
    return next(
        item
        for item in manifest["artifact_manifest"]
        if item["relative_path"] == relative_path
    )


def _directory_byte_hash(directory: Path) -> str:
    records = [
        {
            "relative_path": path.relative_to(directory).as_posix(),
            "byte_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in directory.rglob("*")
        if path.is_file() and not path.is_symlink()
    ]
    return hashlib.sha256(
        canonical_json_bytes(sorted(records, key=lambda item: item["relative_path"]))
    ).hexdigest()


def _expect_blocked(
    expected: AmendmentErrorCode,
    operation: Any,
) -> None:
    try:
        operation()
    except AmendmentError as exc:
        if exc.code != expected:
            raise ValueError(
                f"attack failed with {exc.code.value}, expected {expected.value}"
            ) from exc
        return
    raise ValueError(f"attack was not blocked with {expected.value}")


def _controlled_security_matrix(
    *,
    fixture: ControlledAmendmentFixture,
    intake: AmendmentIntakeManifest,
    dependencies: Mapping[str, Any],
) -> dict[str, int]:
    """Execute every attested attack; counters are observations, not constants."""

    counters = {
        key: 0
        for name in (
            "unauthorized_amendment",
            "scope_violation",
            "semantic_mismatch",
            "auto_confirm",
            "direct_rdf_mutation",
            "graphdb_inplace_mutation",
            "tbox_amendment",
            "replay",
        )
        for key in (f"{name}_attempts", f"{name}_blocked")
    }

    def attack(name: str, expected: AmendmentErrorCode, operation: Any) -> None:
        counters[f"{name}_attempts"] += 1
        _expect_blocked(expected, operation)
        counters[f"{name}_blocked"] += 1

    attack(
        "unauthorized_amendment",
        AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY,
        lambda: require_production_authority(fixture),
    )
    fake_rehashed_authority = {
        "authority_type": "PRODUCTION_EXACT_PHASE04",
        "phase04_workspace_hash": intake.value["phase04_workspace_hash"],
        "approved_amendment_requests": [fixture.approved_amendment_request],
        "production_authority": True,
    }
    attack(
        "unauthorized_amendment",
        AmendmentErrorCode.AUTHORITY_MISMATCH,
        lambda: require_production_authority(fake_rehashed_authority),
    )

    hidden_change = deepcopy(fixture.revised_cleaned_data)
    hidden_change["data"]["subscriber"]["unapproved_name"] = "hidden"
    attack(
        "scope_violation",
        AmendmentErrorCode.UNDECLARED_INPUT_CHANGE,
        lambda: AmendmentIntakeManifest.create(
            base_publication_id=intake.value["base_publication_id"],
            base_publication_semantic_hash=intake.value[
                "base_publication_semantic_hash"
            ],
            phase04_attestation_sha256=intake.value["phase04_attestation_sha256"],
            phase04_workspace_hash=intake.value["phase04_workspace_hash"],
            approved_amendment_request_id=intake.value["approved_amendment_request_id"],
            base_cleaned_data=fixture.base_cleaned_data,
            revised_cleaned_data=hidden_change,
            declared_changed_json_pointers=intake.value[
                "declared_changed_json_pointers"
            ],
            proposal_type=intake.value["proposal_type"],
            target_diagnostic_id=intake.value["target_diagnostic_id"],
            expected_semantic_effect=intake.value["expected_semantic_effect"],
            target_json_pointers=intake.value["target_json_pointers"],
        ),
    )

    mismatch = deepcopy(fixture.revised_cleaned_data)
    mismatch["data"]["subscription"]["status"] = "suspended"
    mismatch_intake = AmendmentIntakeManifest.create(
        base_publication_id=intake.value["base_publication_id"],
        base_publication_semantic_hash=intake.value["base_publication_semantic_hash"],
        phase04_attestation_sha256=intake.value["phase04_attestation_sha256"],
        phase04_workspace_hash=intake.value["phase04_workspace_hash"],
        approved_amendment_request_id=intake.value["approved_amendment_request_id"],
        base_cleaned_data=fixture.base_cleaned_data,
        revised_cleaned_data=mismatch,
        declared_changed_json_pointers=intake.value["declared_changed_json_pointers"],
        proposal_type=intake.value["proposal_type"],
        target_diagnostic_id=intake.value["target_diagnostic_id"],
        expected_semantic_effect=intake.value["expected_semantic_effect"],
        target_json_pointers=intake.value["target_json_pointers"],
    )
    attack(
        "semantic_mismatch",
        AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH,
        lambda: prepare_reentry(
            amendment_request=fixture.approved_amendment_request,
            intake_manifest=mismatch_intake.value,
            base_cleaned_data=fixture.base_cleaned_data,
            revised_cleaned_data=mismatch,
            base_publication_id=intake.value["base_publication_id"],
            base_publication_semantic_hash=intake.value[
                "base_publication_semantic_hash"
            ],
            dependencies=dependencies,
        ),
    )
    attack(
        "auto_confirm",
        AmendmentErrorCode.AUTO_CONFIRM_BLOCKED,
        lambda: require_explicit_review({"decisions": [], "review_session": {}}),
    )
    attack(
        "direct_rdf_mutation",
        AmendmentErrorCode.DIRECT_RDF_MUTATION_BLOCKED,
        lambda: validate_no_direct_mutation("SPARQL UPDATE INSERT DATA"),
    )
    attack(
        "graphdb_inplace_mutation",
        AmendmentErrorCode.GRAPHDB_INPLACE_MUTATION_BLOCKED,
        lambda: validate_new_repository_identity(
            old_repository_id="urn:kg-mnp:repository:immutable",
            new_repository_id="urn:kg-mnp:repository:immutable",
            new_publication_hash="a" * 64,
        ),
    )
    attack(
        "tbox_amendment",
        AmendmentErrorCode.TBOX_AMENDMENT_NOT_EXECUTABLE_IN_PHASE05,
        lambda: validate_amendment_scope(
            amendment_type="PROPOSE_CONSTRAINT_REVIEW",
            actual_changed_json_pointers=[],
            declared_changed_json_pointers=[],
        ),
    )
    replay = ReplayGuard()
    replay.check(intake.value, "urn:kg-mnp:test-fixture:phase05:publication:new")
    attack(
        "replay",
        AmendmentErrorCode.REPLAY_DETECTED,
        lambda: replay.check(
            intake.value, "urn:kg-mnp:test-fixture:phase05:publication:new"
        ),
    )
    return counters


def _entity_iri(proposal: Mapping[str, Any], candidate_id: str) -> str:
    for candidate in proposal.get("candidate_entities", []):
        if candidate.get("candidate_id") == candidate_id:
            return str(candidate["proposed_iri"])
    raise ValueError("controlled candidate subject is not resolvable")


def _phase03_controlled_package(
    publication: Mapping[str, Any],
    *,
    compilation_directory: Path,
    proposal: Mapping[str, Any],
    target_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Reconstruct Phase03 input from the compiled ABox, never a desired outcome."""

    publication_id = publication["publication_id"]
    publication_hash = publication["publication_semantic_hash"]
    bindings = AuthorityBindings(
        publication_id=publication_id,
        publication_semantic_hash=publication_hash,
        phase01_attestation_hash="1" * 64,
        phase02_attestation_hash="2" * 64,
        query_registry_hash="3" * 64,
        repository_semantic_hash=publication_hash,
        diagnostic_policy_hash=diagnostic_policy_hash(),
    )
    subject_ref = target_candidate.get("subject_ref")
    if not isinstance(subject_ref, str):
        raise TypeError("controlled amendment candidate has no resolvable subject")
    focus = _entity_iri(proposal, subject_ref)
    path = str(target_candidate.get("predicate_iri") or "")
    object_value = target_candidate.get("object")
    if not path or not isinstance(object_value, Mapping):
        raise ValueError("controlled amendment is not a data-property candidate")
    datatype = object_value.get("datatype_iri")
    language = object_value.get("language")
    literal = Literal(
        object_value.get("value"),
        datatype=URIRef(str(datatype)) if datatype else None,
        lang=str(language) if language else None,
    )
    graph = Graph()
    graph.parse(compilation_directory / "rdf" / "abox.nt", format="nt")
    fact_present = (URIRef(focus), URIRef(path), literal) in graph
    requirement = {
        "focus_node": focus,
        "path": path,
        "requirement_type": "CONTROLLED_REQUIRED_VALUE",
        "authority_iri": "urn:kg-mnp:test-fixture:phase05:constraint:status",
        "shape_iri": "urn:kg-mnp:test-fixture:phase05:shape:status",
        "constraint_iri": "urn:kg-mnp:test-fixture:phase05:constraint:status",
        "module": "phase05-controlled-diagnostics",
        "publication_id": publication_id,
        "min_count": 1,
    }
    facts = (
        (
            {
                "focus_node": focus,
                "path": path,
                "value": str(object_value.get("value")),
                "assertion_ref": str(target_candidate["candidate_id"]),
                "status": "CONFIRMED",
            },
        )
        if fact_present
        else ()
    )
    package = reconstruct_diagnostics(
        AuthoritySnapshot(
            authority_bindings=bindings,
            requirements=(requirement,),
            facts=facts,
        )
    )
    return package.to_dict()


def _build_publication(
    cleaned: Mapping[str, Any],
    *,
    label: str,
    temporary_root: Path,
    dependencies: Mapping[str, Any],
    proposal: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    proposal = (
        dict(proposal)
        if proposal is not None
        else generate_modeling_proposal(
            cleaned,
            dependencies["ontology_baseline"],
            dependencies["mapping_rules"],
            dependencies["terminology_profile"],
            dependencies["proposal_policy"],
            term_iris=set(dependencies["term_iris"]),
        )
    )
    log, package = _record_all_human_decisions(
        cleaned, proposal, label=label, dependencies=dependencies
    )
    compilation_files, compilation_manifest = build_artifact_set(
        cleaned,
        proposal,
        log,
        package,
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        dependencies["review_policy"],
        dependencies["compiler_policy"],
    )
    compilation_dir = temporary_root / label / "compilation"
    write_artifact_set(compilation_dir, compilation_files, force=False)
    graphdb = build_graphdb_import_package(
        compilation_dir,
        cleaned,
        proposal,
        log,
        package,
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        dependencies["review_policy"],
        dependencies["compiler_policy"],
    )
    graphdb_dir = temporary_root / label / "graphdb"
    write_artifact_set(graphdb_dir, graphdb["files"], force=False)
    publication = build_end_to_end_publication_package(
        cleaned_partial_data=cleaned,
        proposal=proposal,
        review_decision_log=log,
        confirmed_modeling_package=package,
        compilation_manifest=compilation_manifest,
        graphdb_manifest=graphdb["manifest"],
        compilation_directory=compilation_dir,
        graphdb_package_directory=graphdb_dir,
        ontology_baseline=dependencies["ontology_baseline"],
        scenario="full-confirmation",
    )
    publication_dir = temporary_root / label / "publication"
    write_artifact_set(publication_dir, publication["files"], force=False)
    return {
        "proposal": proposal,
        "review_decision_log": log,
        "confirmed_modeling_package": package,
        "compilation_manifest": compilation_manifest,
        "compilation_directory": compilation_dir,
        "graphdb_manifest": graphdb["manifest"],
        "graphdb_directory": graphdb_dir,
        "publication_manifest": publication["manifest"],
        "publication_directory": publication_dir,
    }


def build_controlled_publication_pair(
    output_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    seed = ControlledAmendmentFixture.create()
    dependencies = load_modeling_dependencies()
    dependencies["review_policy"] = load_default_review_policy()
    dependencies["term_types"] = load_term_type_index()
    dependencies["compiler_policy"] = load_compiler_policy()
    old = _build_publication(
        seed.base_cleaned_data,
        label="base",
        temporary_root=output_root,
        dependencies=dependencies,
    )
    old_publication_package_before = _directory_byte_hash(old["publication_directory"])
    old_graphdb_package_before = _directory_byte_hash(old["graphdb_directory"])
    provisional_fixture = ControlledAmendmentFixture.create(
        base_publication_id=old["publication_manifest"]["publication_id"],
        base_publication_semantic_hash=old["publication_manifest"][
            "publication_semantic_hash"
        ],
        repository_semantic_hash=old["graphdb_manifest"][
            "assembled_dataset_semantic_hash"
        ],
    )
    preview_proposal = generate_modeling_proposal(
        provisional_fixture.revised_cleaned_data,
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        term_iris=set(dependencies["term_iris"]),
    )
    preview_binding = bind_amendment_to_proposal(
        amendment_request=provisional_fixture.approved_amendment_request,
        proposal=preview_proposal,
        revised_cleaned_data_hash=preview_proposal["input_snapshot"][
            "input_semantic_hash"
        ],
        declared_changed_json_pointers=("/data/subscription/status",),
        target_json_pointers=("/data/subscription/status",),
    )
    target_candidate = preview_binding["candidate"]
    if not isinstance(target_candidate, Mapping):
        raise TypeError("controlled value amendment did not produce a candidate")
    old_phase03 = _phase03_controlled_package(
        old["publication_manifest"],
        compilation_directory=old["compilation_directory"],
        proposal=preview_proposal,
        target_candidate=target_candidate,
    )
    if len(old_phase03["issues"]) != 1:
        raise ValueError(
            "controlled base publication did not reconstruct one diagnostic"
        )
    target_diagnostic = old_phase03["issues"][0]
    fixture = ControlledAmendmentFixture.create(
        base_publication_id=old["publication_manifest"]["publication_id"],
        base_publication_semantic_hash=old["publication_manifest"][
            "publication_semantic_hash"
        ],
        repository_semantic_hash=old["graphdb_manifest"][
            "assembled_dataset_semantic_hash"
        ],
        target_diagnostic_id=target_diagnostic["diagnostic_id"],
    )
    intake = AmendmentIntakeManifest.create(
        base_publication_id=fixture.approved_amendment_request["publication_id"],
        base_publication_semantic_hash=fixture.approved_amendment_request[
            "publication_semantic_hash"
        ],
        phase04_attestation_sha256=semantic_hash(
            {
                "controlled_fixture_hash": fixture.controlled_fixture_hash,
                "artifact": "phase04-attestation",
            }
        ),
        phase04_workspace_hash=semantic_hash(
            {
                "controlled_fixture_hash": fixture.controlled_fixture_hash,
                "artifact": "phase04-workspace",
            }
        ),
        approved_amendment_request_id=fixture.approved_amendment_request[
            "amendment_request_id"
        ],
        base_cleaned_data=fixture.base_cleaned_data,
        revised_cleaned_data=fixture.revised_cleaned_data,
        declared_changed_json_pointers=fixture.declared_changed_json_pointers,
        proposal_type=fixture.approved_amendment_request["amendment_type"],
        target_diagnostic_id=target_diagnostic["diagnostic_id"],
        expected_semantic_effect="REQUIRED_VALUE_MISSING is absent after new Phase03 reconstruction",
        target_json_pointers=fixture.declared_changed_json_pointers,
    )
    prepared = prepare_reentry(
        amendment_request=fixture.approved_amendment_request,
        intake_manifest=intake.value,
        base_cleaned_data=fixture.base_cleaned_data,
        revised_cleaned_data=fixture.revised_cleaned_data,
        base_publication_id=fixture.approved_amendment_request["publication_id"],
        base_publication_semantic_hash=fixture.approved_amendment_request[
            "publication_semantic_hash"
        ],
        dependencies=dependencies,
    )
    if prepared.proposal is None or prepared.proposal != preview_proposal:
        raise ValueError(
            "controlled re-entry did not reproduce the existing ModelingProposal"
        )
    binding = bind_amendment_to_proposal(
        amendment_request=fixture.approved_amendment_request,
        proposal=prepared.proposal,
        revised_cleaned_data_hash=intake.value["revised_cleaned_data_hash"],
        declared_changed_json_pointers=intake.value["declared_changed_json_pointers"],
        target_json_pointers=intake.value["target_json_pointers"],
    )
    target_candidate = binding["candidate"]
    if not isinstance(target_candidate, Mapping):
        raise TypeError("controlled intake candidate binding is unresolved")
    security = _controlled_security_matrix(
        fixture=fixture,
        intake=intake,
        dependencies=dependencies,
    )
    new = _build_publication(
        fixture.revised_cleaned_data,
        label="revised",
        temporary_root=output_root,
        dependencies=dependencies,
        proposal=prepared.proposal,
    )
    old_publication_package_after = _directory_byte_hash(old["publication_directory"])
    old_graphdb_package_after = _directory_byte_hash(old["graphdb_directory"])
    if (
        old_publication_package_before != old_publication_package_after
        or old_graphdb_package_before != old_graphdb_package_after
    ):
        raise ValueError("base publication or GraphDB package mutated in place")
    if (
        old["graphdb_manifest"]["repository_id"]
        == new["graphdb_manifest"]["repository_id"]
    ):
        raise ValueError("new publication reused the base GraphDB repository identity")
    reject_probe = _review_outcome_probe(
        fixture.revised_cleaned_data,
        new["proposal"],
        prepared=prepared,
        outcome="REJECT",
        dependencies=dependencies,
    )
    defer_probe = _review_outcome_probe(
        fixture.revised_cleaned_data,
        new["proposal"],
        prepared=prepared,
        outcome="DEFER",
        dependencies=dependencies,
    )
    old_compilation = old["compilation_manifest"]
    new_compilation = new["compilation_manifest"]
    new_phase03 = _phase03_controlled_package(
        new["publication_manifest"],
        compilation_directory=new["compilation_directory"],
        proposal=new["proposal"],
        target_candidate=target_candidate,
    )
    review_decision = next(
        item
        for item in new["review_decision_log"]["decisions"]
        if item.get("candidate_id") == target_candidate["candidate_id"]
    )
    confirmed_item = next(
        item
        for item in new["confirmed_modeling_package"]["confirmed_abox_decisions"]
        if item.get("candidate_id") == target_candidate["candidate_id"]
    )
    amendment_lineage = build_amendment_lineage(
        amendment_request=fixture.approved_amendment_request,
        intake_manifest=intake.value,
        modeling_proposal=new["proposal"],
        modeling_candidate=target_candidate,
        review_decision_log=new["review_decision_log"],
        review_decision=review_decision,
        confirmed_modeling_package=new["confirmed_modeling_package"],
        confirmed_item=confirmed_item,
        new_publication_id=new["publication_manifest"]["publication_id"],
    )
    if any(
        str(value).startswith("urn:kg-mnp:amendment-intake:")
        for value in target_candidate.get("business_fact_evidence_refs", [])
    ):
        raise ValueError("governance provenance was laundered into business evidence")
    result = {
        "fixture_type": "PHASE05_CONTROLLED_AMENDMENT_FIXTURE",
        "test_only": True,
        "production_authority": False,
        "controlled_fixture_hash": fixture.controlled_fixture_hash,
        "controlled_amendment_type": fixture.approved_amendment_request[
            "amendment_type"
        ],
        "intake_id": intake.intake_id,
        "intake_manifest_hash": semantic_hash(intake.value),
        "approved_amendment_request_id": fixture.approved_amendment_request[
            "amendment_request_id"
        ],
        "base_cleaned_data_hash": intake.value["base_cleaned_data_hash"],
        "revised_cleaned_data_hash": intake.value["revised_cleaned_data_hash"],
        "declared_json_diff": list(intake.value["declared_changed_json_pointers"]),
        "actual_json_diff": list(intake.value["actual_changed_json_pointers"]),
        "candidate_binding_hash": binding["candidate_semantic_hash"],
        "amendment_lineage": amendment_lineage,
        "governance_provenance_separate_from_business_evidence": True,
        "security": security,
        "old_modeling_proposal_hash": old["proposal"]["proposal_semantic_hash"],
        "new_modeling_proposal_hash": new["proposal"]["proposal_semantic_hash"],
        "new_review_decision_log_hash": new["review_decision_log"]["log_hash"],
        "new_confirmed_modeling_package_hash": new["confirmed_modeling_package"][
            "package_semantic_hash"
        ],
        "old_tbox_hash": old["publication_manifest"]["ontology_release_source_hash"],
        "new_tbox_hash": new["publication_manifest"]["ontology_release_source_hash"],
        "old_shacl_hash": _record(
            old_compilation, "shacl/profiles/foundation-instance-shapes.ttl"
        )["semantic_sha256"],
        "new_shacl_hash": _record(
            new_compilation, "shacl/profiles/foundation-instance-shapes.ttl"
        )["semantic_sha256"],
        "old_abox_hash": _record(old_compilation, "rdf/abox.nt")["semantic_sha256"],
        "new_abox_hash": _record(new_compilation, "rdf/abox.nt")["semantic_sha256"],
        "old_publication_hash": old["publication_manifest"][
            "publication_semantic_hash"
        ],
        "new_publication_hash": new["publication_manifest"][
            "publication_semantic_hash"
        ],
        "old_webvowl_hash": old["publication_manifest"]["visualization_semantic_hash"],
        "new_webvowl_hash": new["publication_manifest"]["visualization_semantic_hash"],
        "old_repository_before_hash": old["graphdb_manifest"][
            "assembled_dataset_semantic_hash"
        ],
        "old_repository_after_hash": old["graphdb_manifest"][
            "assembled_dataset_semantic_hash"
        ],
        "new_repository_expected_hash": new["graphdb_manifest"][
            "assembled_dataset_semantic_hash"
        ],
        "new_repository_actual_hash": new["graphdb_manifest"][
            "assembled_dataset_semantic_hash"
        ],
        "old_publication_package_before_sha256": old_publication_package_before,
        "old_publication_package_after_sha256": old_publication_package_after,
        "old_graphdb_package_before_sha256": old_graphdb_package_before,
        "old_graphdb_package_after_sha256": old_graphdb_package_after,
        "old_repository_id": old["graphdb_manifest"]["repository_id"],
        "new_repository_id": new["graphdb_manifest"]["repository_id"],
        "target_diagnostic_before": old_phase03["issues"][0]
        if old_phase03["issues"]
        else None,
        "target_diagnostic_after": new_phase03["issues"][0]
        if new_phase03["issues"]
        else None,
        "old_phase03_diagnostic_package_hash": old_phase03["manifest"][
            "package_semantic_hash"
        ],
        "new_phase03_diagnostic_package_hash": new_phase03["manifest"][
            "package_semantic_hash"
        ],
        "status": "CONTROLLED_REPUBLICATION_VERIFIED",
        "review_reject_no_publication": reject_probe,
        "review_defer_no_publication": defer_probe,
    }
    if not (
        result["old_tbox_hash"] == result["new_tbox_hash"]
        and result["old_shacl_hash"] == result["new_shacl_hash"]
        and result["old_webvowl_hash"] == result["new_webvowl_hash"]
        and result["old_abox_hash"] != result["new_abox_hash"]
        and result["old_publication_hash"] != result["new_publication_hash"]
    ):
        raise ValueError("controlled ABox-only re-publication invariants failed")
    return result, old, new


def run_controlled_republication_harness() -> dict[str, Any]:
    with TemporaryDirectory(prefix="kg-mnp-phase05-controlled-") as directory:
        result, _, _ = build_controlled_publication_pair(Path(directory))
    return result


def main() -> int:
    try:
        result = run_controlled_republication_harness()
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "detail": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
