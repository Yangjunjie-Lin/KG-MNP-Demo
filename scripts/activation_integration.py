#!/usr/bin/env python3
"""Licensed Application Phase 06 activation/rollback integration closure."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from kg_mnp_demo.activation.artifact_verifier import (
    verify_application_phase06_artifact,
)
from kg_mnp_demo.activation.attestation import publication_tree_sha256
from kg_mnp_demo.activation.authority_binding import (
    ControlledPhase06Authority,
    load_production_phase06_authority,
    require_production_phase06_authority,
)
from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.activation.event_log import event_identity_content
from kg_mnp_demo.activation.execution import (
    ActivationController,
    ReadOnlyGraphDBTargetVerifier,
)
from kg_mnp_demo.activation.persistence import ActivationStateStore
from kg_mnp_demo.activation.registry import registry_semantic_content
from kg_mnp_demo.activation.reporting import (
    aggregate_probe_records,
    build_application_phase06_attestation,
    build_probe_record,
)
from kg_mnp_demo.activation.security import (
    freeze_state_directory,
    validate_control_plane_payload,
)
from kg_mnp_demo.activation.validator import (
    validate_activation_registry_against_authorities,
)
from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient
from kg_mnp_demo.graphdb.client import GraphDBClient, GraphDBClientError
from kg_mnp_demo.graphdb.importer import import_package
from kg_mnp_demo.graphdb.verifier import verify_imported_repository
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

if __package__:
    from scripts import graphdb_integration as graphdb_runtime
    from scripts.activation_controlled_fixture import (
        build_controlled_activation_fixture,
        run_controlled_activation_workflow,
        run_controlled_process_race,
    )
else:
    import graphdb_integration as graphdb_runtime  # type: ignore[import-not-found]
    from activation_controlled_fixture import (  # type: ignore[import-not-found]
        build_controlled_activation_fixture,
        run_controlled_activation_workflow,
        run_controlled_process_race,
    )


def _git_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _discover_defaults(args: argparse.Namespace) -> None:
    stage08 = Path("runtime_outputs/publication") / args.publication_scenario
    manifest_path = stage08 / "publication-manifest.json"
    if not manifest_path.is_file():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        publication_hash = manifest["publication_semantic_hash"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return
    args.publication_package = args.publication_package or stage08
    args.publication_attestation = args.publication_attestation or (
        Path("runtime_reports/publication")
        / publication_hash
        / "publication-attestation.json"
    )
    args.phase01_artifact = args.phase01_artifact or (
        Path("runtime_reports/application") / publication_hash
    )
    args.phase02_artifact = args.phase02_artifact or (
        Path("runtime_reports/workbench") / publication_hash
    )
    args.phase03_artifact = args.phase03_artifact or (
        Path("runtime_reports/diagnostics") / publication_hash
    )
    phase04 = sorted(
        Path("runtime_reports/governance").glob(
            "**/application-phase04-attestation.json"
        )
    )
    if phase04:
        args.phase04_artifact = args.phase04_artifact or phase04[-1].parent
    args.phase05_artifact = args.phase05_artifact or (
        Path("runtime_reports/amendment") / args.expected_commit_sha
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-package", type=Path)
    parser.add_argument("--publication-attestation", type=Path)
    parser.add_argument("--phase01-artifact", type=Path)
    parser.add_argument("--phase02-artifact", type=Path)
    parser.add_argument("--phase03-artifact", type=Path)
    parser.add_argument("--phase04-artifact", type=Path)
    parser.add_argument("--phase05-artifact", type=Path)
    parser.add_argument("--expected-commit-sha")
    parser.add_argument("--publication-scenario", default="full-confirmation")
    parser.add_argument("--artifact-output", type=Path)
    return parser


def _authority_arguments(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "publication_package_directory": args.publication_package,
        "publication_attestation_path": args.publication_attestation,
        "phase01_artifact_directory": args.phase01_artifact,
        "phase02_artifact_directory": args.phase02_artifact,
        "phase03_artifact_directory": args.phase03_artifact,
        "phase04_artifact_directory": args.phase04_artifact,
        "phase05_artifact_directory": args.phase05_artifact,
        "expected_commit_sha": args.expected_commit_sha,
        "publication_scenario": args.publication_scenario,
    }


def _probe(
    records: list[dict[str, Any]],
    *,
    attack: str,
    expected_code: ActivationErrorCode | str,
    details: str,
    operation: Callable[[], Any],
) -> None:
    expected = str(expected_code)
    try:
        operation()
    except ActivationError as exc:
        observed = exc.code.value
    else:
        observed = "NO_ERROR"
    blocked = observed == expected
    records.append(
        build_probe_record(
            attack=attack,
            expected_code=expected,
            observed_code=observed,
            blocked=blocked,
            details=details,
        )
    )
    if not blocked:
        raise ValueError(
            f"security probe {details!r} observed {observed}, expected {expected}"
        )


def _review_probe(
    records: list[dict[str, Any]],
    *,
    details: str,
    expected: str,
    observed: str,
) -> None:
    records.append(
        build_probe_record(
            attack="activation_review",
            expected_code=expected,
            observed_code=observed,
            blocked=False,
            details=details,
        )
    )
    if observed != expected:
        raise ValueError(
            f"activation review probe {details!r} observed {observed}, expected {expected}"
        )


def _supplemental_probe(
    *, attack: str, expected: str, observed: str, details: str
) -> dict[str, Any]:
    content = {
        "attack": attack,
        "expected_code": expected,
        "observed_code": observed,
        "blocked": observed == expected,
        "details": details,
    }
    return {
        "probe_id": "urn:kg-mnp:test-fixture:phase06:supplemental-probe:"
        + semantic_hash(content),
        **content,
    }


def _rehash_registry(value: dict[str, Any]) -> None:
    previous = "GENESIS"
    for event in value["events"]:
        event["previous_event_hash"] = previous
        event["payload_hash"] = semantic_hash(event["payload"])
        event["event_hash"] = semantic_hash(event_identity_content(event))
        event["event_id"] = (
            "urn:kg-mnp:test-fixture:phase06:activation-event:"
            if event["test_only"]
            else "urn:kg-mnp:activation-event:"
        ) + event["event_hash"]
        previous = event["event_hash"]
    value["registry_revision"] = len(value["events"])
    value["head_event_hash"] = previous
    value["registry_hash"] = semantic_hash(registry_semantic_content(value))


def _wait_graphdb(client: GraphDBClient) -> None:
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            if client.health_check().get("healthy") is True:
                return
        except (GraphDBClientError, OSError, ValueError):
            pass
        time.sleep(3)
    raise RuntimeError("GraphDB did not become healthy within 240 seconds")


def _start_graphdb(
    fixture_hash: str,
) -> tuple[str, GraphDBClient, Path | None, Path | None]:
    project = "kgmnp-activation-" + fixture_hash[:12]
    override: Path | None = None
    generated: Path | None = None
    client = GraphDBClient(timeout=15.0, retries=1)
    compose_attempted = False
    try:
        license_path, source_type = graphdb_runtime._license_runtime_file(fixture_hash)
        generated = license_path if source_type in {"CONTENT", "B64"} else None
        if license_path is not None:
            override = (
                Path("runtime_outputs/activation")
                / f".compose-license-{fixture_hash}.yml"
            ).resolve()
            override.parent.mkdir(parents=True, exist_ok=True)
            override.write_text(
                "services:\n  graphdb:\n    volumes:\n"
                f"      - '{license_path.as_posix()}:/opt/graphdb/home/conf/graphdb.license:ro'\n",
                encoding="utf-8",
            )
            graphdb_runtime.COMPOSE_FILES.append(override)
        compose_attempted = True
        graphdb_runtime._compose(project, "up", "-d")
        _wait_graphdb(client)
        readiness = client.verify_runtime_readiness(expected_product_version="11.4.2")
        if readiness.get("license_state") != "ACCEPTED":
            raise RuntimeError("licensed GraphDB readiness verification failed")
        return project, client, override, generated
    except (
        GraphDBClientError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        if compose_attempted:
            try:
                _cleanup_graphdb(
                    project=project,
                    client=client,
                    repository_ids=(),
                    override=override,
                    generated=generated,
                )
            except ActivationError as cleanup_exc:
                raise cleanup_exc from exc
        else:
            try:
                graphdb_runtime._cleanup_license_runtime_files(override, generated)
            except OSError as cleanup_exc:
                raise ActivationError(
                    ActivationErrorCode.INTEGRATION_CLEANUP_FAILED,
                    "temporary license cleanup failed after GraphDB startup error",
                ) from cleanup_exc
        raise


def _compose_resource_ids(project: str) -> tuple[str, ...]:
    file_args: list[str] = []
    for compose_file in graphdb_runtime.COMPOSE_FILES:
        file_args.extend(["-f", str(compose_file)])
    completed = subprocess.run(
        ["docker", "compose", "-p", project, *file_args, "ps", "--all", "-q"],
        cwd=graphdb_runtime.ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("controlled Compose cleanup verification failed")
    return tuple(line for line in completed.stdout.splitlines() if line.strip())


def _cleanup_graphdb(
    *,
    project: str,
    client: GraphDBClient,
    repository_ids: tuple[str, ...],
    override: Path | None,
    generated: Path | None,
) -> dict[str, Any]:
    failures: list[str] = []
    for repository_id in reversed(repository_ids):
        try:
            if repository_id in client.list_repositories():
                client.delete_generated_repository(repository_id)
        except (GraphDBClientError, OSError, ValueError):
            failures.append(f"controlled repository cleanup failed: {repository_id}")
    if repository_ids:
        try:
            remaining = set(repository_ids).intersection(client.list_repositories())
            if remaining:
                failures.append("controlled repository cleanup verification failed")
        except (GraphDBClientError, OSError, ValueError):
            failures.append("controlled repository cleanup verification failed")
    try:
        completed = graphdb_runtime._compose(
            project, "down", "-v", "--remove-orphans", check=False
        )
        if completed.returncode != 0:
            failures.append("controlled Compose cleanup failed")
    except (OSError, subprocess.SubprocessError):
        failures.append("controlled Compose cleanup failed")
    try:
        if _compose_resource_ids(project):
            failures.append("controlled Compose cleanup verification failed")
    except (OSError, RuntimeError, subprocess.SubprocessError):
        failures.append("controlled Compose cleanup verification failed")
    try:
        graphdb_runtime._cleanup_license_runtime_files(override, generated)
    except OSError:
        failures.append("temporary license cleanup failed")
    result = {
        "controlled_repository_count": len(repository_ids),
        "cleanup_failures": len(failures),
        "status": "PASS" if not failures else "INTEGRATION_CLEANUP_FAILED",
    }
    if failures:
        raise ActivationError(
            ActivationErrorCode.INTEGRATION_CLEANUP_FAILED, "; ".join(failures)
        )
    return result


def _approve_p1(
    controller: ActivationController, authority: ControlledPhase06Authority
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = controller.status()
    proposal = controller.create_proposal(
        target_publication_id=authority.activation_candidates[0].publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Approved controlled repository attack precondition.",
        created_by_label="Phase06 controlled deployment operator label",
        explicit_human_intent=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    state = controller.status()
    controller.submit_proposal(
        proposal["activation_proposal_id"],
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    state = controller.status()
    decision = controller.record_review(
        proposal["activation_proposal_id"],
        decision="APPROVE_FOR_ACTIVATION",
        reviewed_by_label="Phase06 controlled human reviewer label",
        review_note="Explicit human approval for a fail-closed repository probe.",
        explicit_human_action=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    return proposal, decision


def _repository_attack_probes(
    *,
    fixture: dict[str, Any],
    client: GraphDBClient,
    verifier: ReadOnlyGraphDBTargetVerifier,
    state_directory: Path,
    records: list[dict[str, Any]],
) -> None:
    authority = fixture["authority"]
    p1 = authority.activation_candidates[0]
    controller = ActivationController(
        ActivationStateStore(state_directory, authority), verifier
    )
    controller.initialize()
    proposal, decision = _approve_p1(controller, authority)
    pointer = controller.status()["current_pointer"]

    client.delete_generated_repository(p1.repository_id)
    _probe(
        records,
        attack="missing_repository",
        expected_code=ActivationErrorCode.TARGET_REPOSITORY_UNAVAILABLE,
        details="Deleted controlled P1 before activation and observed fail-closed execution.",
        operation=lambda: controller.execute(
            proposal["activation_proposal_id"],
            decision["activation_review_decision_id"],
            expected_generation=pointer["generation"],
            expected_pointer_hash=pointer["pointer_hash"],
        ),
    )
    if controller.status()["current_pointer"] != pointer:
        raise ValueError("missing-repository probe changed the pointer")
    import_package(client, fixture["new"]["graphdb_directory"])
    verify_imported_repository(client, fixture["new"]["graphdb_directory"])

    client.import_nquads(
        p1.repository_id,
        b"<urn:kg-mnp:test-fixture:phase06:drift:s> "
        b'<urn:kg-mnp:test-fixture:phase06:drift:p> "drift" '
        b"<urn:kg-mnp:test-fixture:phase06:drift:g> .\n",
    )
    _probe(
        records,
        attack="repository_mismatch",
        expected_code=ActivationErrorCode.TARGET_REPOSITORY_HASH_MISMATCH,
        details="Added one controlled live quad and observed repository hash mismatch.",
        operation=lambda: controller.execute(
            proposal["activation_proposal_id"],
            decision["activation_review_decision_id"],
            expected_generation=pointer["generation"],
            expected_pointer_hash=pointer["pointer_hash"],
        ),
    )
    if controller.status()["current_pointer"] != pointer:
        raise ValueError("repository-mismatch probe changed the pointer")
    client.delete_generated_repository(p1.repository_id)
    import_package(client, fixture["new"]["graphdb_directory"])
    verify_imported_repository(client, fixture["new"]["graphdb_directory"])


def _non_repository_security_probes(
    *,
    fixture: dict[str, Any],
    workflow: dict[str, Any],
    state_directory: Path,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    authority = fixture["authority"]
    verifier = fixture["offline_verifier"]
    supplemental: list[dict[str, Any]] = []

    _probe(
        records,
        attack="fixture_laundering",
        expected_code=(
            ActivationErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET
        ),
        details="Passed the controlled Phase06 authority to the production authority gate.",
        operation=lambda: require_production_phase06_authority(authority),
    )
    _probe(
        records,
        attack="fixture_laundering",
        expected_code=ActivationErrorCode.AUTHORITY_MISMATCH,
        details="Passed a caller-created fake Phase05 lineage object to the production gate.",
        operation=lambda: require_production_phase06_authority(
            {"authority_type": "PRODUCTION_EXACT_PHASE05"}
        ),
    )

    fresh = ActivationController(
        ActivationStateStore(state_directory / "requests", authority), verifier
    )
    fresh.initialize()
    request_state = fresh.status()
    _probe(
        records,
        attack="unverified_target",
        expected_code=ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET,
        details="Requested activation of a hash-shaped publication outside Phase05 lineage.",
        operation=lambda: fresh.create_proposal(
            target_publication_id=(
                "urn:kg-mnp:test-fixture:phase06:publication:" + "9" * 64
            ),
            activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
            rationale="Unverified target attack.",
            created_by_label="controlled attacker label",
            explicit_human_intent=True,
            expected_registry_revision=request_state["registry_revision"],
            expected_head_event_hash=request_state["head_event_hash"],
        ),
    )
    _probe(
        records,
        attack="unknown_rollback",
        expected_code=ActivationErrorCode.UNKNOWN_ROLLBACK_TARGET,
        details="Requested rollback to a publication absent from bootstrap and history.",
        operation=lambda: fresh.propose_rollback(
            target_publication_id=(
                "urn:kg-mnp:test-fixture:phase06:publication:" + "8" * 64
            ),
            rationale="Unknown rollback target attack.",
            created_by_label="controlled attacker label",
            explicit_human_intent=True,
            expected_registry_revision=request_state["registry_revision"],
            expected_head_event_hash=request_state["head_event_hash"],
        ),
    )
    automatic = fresh.create_proposal(
        target_publication_id=authority.activation_candidates[0].publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Automatic activation attack precondition.",
        created_by_label="controlled attacker label",
        explicit_human_intent=True,
        expected_registry_revision=request_state["registry_revision"],
        expected_head_event_hash=request_state["head_event_hash"],
    )
    automatic_pointer = fresh.status()["current_pointer"]
    _probe(
        records,
        attack="auto_activation",
        expected_code=ActivationErrorCode.HUMAN_ACTIVATION_APPROVAL_REQUIRED,
        details="Attempted execution without an explicit human activation review.",
        operation=lambda: fresh.execute(
            automatic["activation_proposal_id"],
            "urn:kg-mnp:test-fixture:phase06:activation-review-decision:" + "0" * 64,
            expected_generation=automatic_pointer["generation"],
            expected_pointer_hash=automatic_pointer["pointer_hash"],
        ),
    )
    graph_mutation_attacks = (
        (
            "Injected a SPARQL UPDATE field into an activation payload.",
            {"sparql_update": "INSERT DATA { <urn:s> <urn:p> <urn:o> }"},
        ),
        (
            "Injected an RDF patch field into an activation payload.",
            {"rdf_patch": "A <urn:s> <urn:p> <urn:o> ."},
        ),
        (
            "Injected a GraphDB URL field into an activation payload.",
            {"graphdb_url": "http://127.0.0.1:7200"},
        ),
        (
            "Injected a repository command field into an activation payload.",
            {"repository_command": "delete controlled repository"},
        ),
    )
    for details, payload in graph_mutation_attacks:
        _probe(
            records,
            attack="direct_graph_mutation",
            expected_code=ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
            details=details,
            operation=lambda payload=payload: validate_control_plane_payload(payload),
        )

    semantic_escalation_attacks = (
        (
            "Attempted to mark deployment metadata as semantic authority.",
            {"semantic_authority": True},
        ),
        (
            "Attempted to inject a confirmed fact into deployment metadata.",
            {"confirmed_fact": True},
        ),
        (
            "Attempted to inject a semantic confirmation review decision.",
            {"review_decision": "CONFIRM"},
        ),
    )
    for details, payload in semantic_escalation_attacks:
        _probe(
            records,
            attack="semantic_escalation",
            expected_code=ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
            details=details,
            operation=lambda payload=payload: validate_control_plane_payload(payload),
        )

    final_registry = workflow["final_registry"]
    final_pointer = workflow["final_pointer"]
    final_hash = workflow["final_state"]["registry_hash"]
    final_head = workflow["final_state"]["head_event_hash"]

    pointer_attack = deepcopy(final_pointer)
    pointer_attack["active_publication_id"] = (
        "urn:kg-mnp:test-fixture:phase06:publication:attacker"
    )
    pointer_attack["active_repository_id"] = "kg-mnp-controlled-attacker"
    pointer_attack["generation"] += 1
    pointer_attack["previous_pointer_hash"] = "0" * 64
    pointer_attack["pointer_hash"] = semantic_hash(
        {key: value for key, value in pointer_attack.items() if key != "pointer_hash"}
    )
    _probe(
        records,
        attack="pointer_tamper",
        expected_code=ActivationErrorCode.REGISTRY_TAMPERED,
        details=(
            "Changed active publication, repository, generation, and predecessor, "
            "then rehashed the pointer."
        ),
        operation=lambda: validate_activation_registry_against_authorities(
            final_registry, authority, current_pointer=pointer_attack
        ),
    )

    event_attacks: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        (
            "Inserted one duplicate event into the activation history.",
            lambda value: value["events"].insert(1, deepcopy(value["events"][1])),
        ),
        (
            "Deleted one event from the activation history.",
            lambda value: value["events"].pop(1),
        ),
        (
            "Reordered two events in the activation history.",
            lambda value: value["events"].__setitem__(
                slice(1, 3), list(reversed(value["events"][1:3]))
            ),
        ),
        (
            "Modified one activation review payload without authority.",
            lambda value: value["events"][3]["payload"].__setitem__(
                "review_note", "attacker replacement"
            ),
        ),
    ]
    for details, mutate in event_attacks:
        attacked = deepcopy(final_registry)
        mutate(attacked)
        _probe(
            records,
            attack="event_rehash",
            expected_code=ActivationErrorCode.REGISTRY_TAMPERED,
            details=details,
            operation=lambda attacked=attacked: (
                validate_activation_registry_against_authorities(
                    attacked, authority, current_pointer=final_pointer
                )
            ),
        )

    rehashed = deepcopy(final_registry)
    review_event = next(
        event
        for event in rehashed["events"]
        if event["event_type"] == "ActivationReviewApproved"
    )
    review_event["payload"]["review_note"] = "Attacker-replaced activation review."
    _rehash_registry(rehashed)
    _probe(
        records,
        attack="event_rehash",
        expected_code=ActivationErrorCode.REGISTRY_TAMPERED,
        details="Altered an activation review, fully rehashed history, and tested trusted anchors.",
        operation=lambda: validate_activation_registry_against_authorities(
            rehashed,
            authority,
            current_pointer=final_pointer,
            expected_registry_hash=final_hash,
            expected_head_event_hash=final_head,
        ),
    )

    replay_controller = ActivationController(
        ActivationStateStore(state_directory.parent / "main-state", authority), verifier
    )
    activation = workflow["activation_proposal"]
    activation_decision = workflow["activation_review_decision"]
    _probe(
        records,
        attack="stale_pointer",
        expected_code=ActivationErrorCode.ACTIVATION_CONCURRENCY_CONFLICT,
        details="Repeated execution against stale generation zero after rollback.",
        operation=lambda: replay_controller.execute(
            activation["activation_proposal_id"],
            activation_decision["activation_review_decision_id"],
            expected_generation=0,
            expected_pointer_hash=workflow["initial_pointer"]["pointer_hash"],
        ),
    )
    _probe(
        records,
        attack="replay",
        expected_code=ActivationErrorCode.REPLAY_DETECTED,
        details="Replayed an applied activation against the current pointer generation.",
        operation=lambda: replay_controller.execute(
            activation["activation_proposal_id"],
            activation_decision["activation_review_decision_id"],
            expected_generation=final_pointer["generation"],
            expected_pointer_hash=final_pointer["pointer_hash"],
        ),
    )

    try:
        freeze_state_directory(Path("%252e%252e/controlled-path-attack"))
    except ActivationError as exc:
        supplemental.append(
            _supplemental_probe(
                attack="double_encoded_path",
                expected="PATH_REJECTED",
                observed=exc.code.value,
                details="Rejected a double-encoded parent traversal state path.",
            )
        )
    else:
        raise ValueError("double-encoded path attack was not blocked")

    with TemporaryDirectory(prefix="kg-mnp-phase06-symlink-probe-") as directory:
        base = Path(directory)
        target = base / "target"
        target.mkdir()
        link = base / "state-link"
        try:
            link.symlink_to(target, target_is_directory=True)
            freeze_state_directory(link)
        except ActivationError as exc:
            supplemental.append(
                _supplemental_probe(
                    attack="symlink_escape",
                    expected="PATH_REJECTED",
                    observed=exc.code.value,
                    details="Rejected a symlink-indirected activation state directory.",
                )
            )
        except OSError as exc:
            raise RuntimeError(
                "integration could not execute the symlink probe"
            ) from exc
        else:
            raise ValueError("symlink state-path attack was not blocked")
    if any(not item["blocked"] for item in supplemental):
        raise ValueError("supplemental path-security probe failed")
    return supplemental


def _repository_hash(client: GraphDBClient, package: Path) -> str:
    return str(verify_imported_repository(client, package)["export_semantic_hash"])


def _artifact_documents(
    *,
    commit_sha: str,
    authority: Any,
    production_initial_registry: dict[str, Any],
    production_initial_pointer: dict[str, Any],
    production_final_registry: dict[str, Any],
    production_final_pointer: dict[str, Any],
    production_final_state: dict[str, Any],
    fixture: dict[str, Any],
    workflow: dict[str, Any],
    probes: list[dict[str, Any]],
    supplemental_probes: list[dict[str, Any]],
    race: dict[str, Any],
    repository_hashes: dict[str, str],
    publication_hashes: dict[str, str],
    cleanup: dict[str, Any],
    determinism_runs: int,
    determinism_passed: int,
) -> dict[str, dict[str, Any]]:
    controlled_authority = fixture["authority"]
    p0 = controlled_authority.base_publication
    p1 = controlled_authority.activation_candidates[0]
    final_state = workflow["final_state"]
    production_pointer_unchanged = bool(
        production_initial_registry == production_final_registry
        and production_initial_pointer == production_final_pointer
    )
    production_evidence = {
        "production_base_publication_id": authority.base_publication.publication_id,
        "production_base_publication_hash": (
            authority.base_publication.publication_semantic_hash
        ),
        "production_base_repository_id": authority.base_publication.repository_id,
        "production_base_repository_hash": (
            authority.base_publication.repository_semantic_hash
        ),
        "production_activation_candidates": (
            authority.production_activation_candidate_count
        ),
        "production_activation_cycles": production_final_state["activation_cycles"],
        "production_rollback_cycles": production_final_state["rollback_cycles"],
        "production_pointer_initial_hash": production_initial_pointer["pointer_hash"],
        "production_pointer_final_hash": production_final_pointer["pointer_hash"],
        "production_pointer_unchanged": production_pointer_unchanged,
    }
    controlled_evidence = {
        "controlled_fixture_hash": controlled_authority.controlled_fixture_hash,
        "controlled_p0_publication_hash": p0.publication_semantic_hash,
        "controlled_p1_publication_hash": p1.publication_semantic_hash,
        "controlled_p0_repository_hash": p0.repository_semantic_hash,
        "controlled_p1_repository_hash": p1.repository_semantic_hash,
        "controlled_activation_cycles": final_state["activation_cycles"],
        "controlled_rollback_cycles": final_state["rollback_cycles"],
        "controlled_initial_generation": workflow["initial_pointer"]["generation"],
        "controlled_post_activation_generation": workflow["post_activation_state"][
            "current_pointer"
        ]["generation"],
        "controlled_final_generation": workflow["final_pointer"]["generation"],
        "p0_repository_before_hash": repository_hashes["p0_before"],
        "p0_repository_after_activation_hash": repository_hashes["p0_after_activation"],
        "p0_repository_after_rollback_hash": repository_hashes["p0_after_rollback"],
        "p1_repository_before_hash": repository_hashes["p1_before"],
        "p1_repository_after_activation_hash": repository_hashes["p1_after_activation"],
        "p1_repository_after_rollback_hash": repository_hashes["p1_after_rollback"],
        "p0_publication_tree_before_hash": publication_hashes["p0_before"],
        "p0_publication_tree_after_hash": publication_hashes["p0_after"],
        "p1_publication_tree_before_hash": publication_hashes["p1_before"],
        "p1_publication_tree_after_hash": publication_hashes["p1_after"],
        "determinism_runs": determinism_runs,
        "determinism_passed": determinism_passed,
    }
    physical_identities = {
        "stage08_identity": authority.stage08_artifact_tree_sha256,
        "phase01_identity": authority.phase01_artifact_tree_sha256,
        "phase02_identity": authority.phase02_artifact_tree_sha256,
        "phase03_identity": authority.phase03_artifact_tree_sha256,
        "phase04_identity": authority.phase04_artifact_tree_sha256,
        "phase05_identity": authority.phase05_artifact_tree_sha256,
    }
    attestation = build_application_phase06_attestation(
        commit_sha=commit_sha,
        physical_identities=physical_identities,
        production_evidence=production_evidence,
        controlled_evidence=controlled_evidence,
        probe_records=probes,
    )
    production_summary = {
        "activation_candidates": authority.production_activation_candidate_count,
        "activation_cycles": production_final_state["activation_cycles"],
        "rollback_cycles": production_final_state["rollback_cycles"],
        "initial_pointer": production_initial_pointer,
        "final_pointer": production_final_pointer,
        "pointer_unchanged": production_pointer_unchanged,
        "bootstrap_registry": production_initial_registry,
        "status": "PRODUCTION_BOOTSTRAP_CURRENT_REFERENCE_VERIFIED",
    }
    controlled_summary = {
        "fixture_id": controlled_authority.fixture_id,
        "controlled_fixture_hash": controlled_authority.controlled_fixture_hash,
        "test_only": True,
        "production_authority": False,
        "p0": p0.descriptor,
        "p1": p1.descriptor,
        "initial_pointer": workflow["initial_pointer"],
        "activation_proposal": workflow["activation_proposal"],
        "activation_review_decision": workflow["activation_review_decision"],
        "activation_receipt": workflow["activation_receipt"],
        "post_activation_pointer": workflow["post_activation_state"]["current_pointer"],
        "resolved_p1": workflow["resolved_p1"],
        "final_registry": workflow["final_registry"],
        "final_pointer": workflow["final_pointer"],
        "status": "CONTROLLED_ACTIVATION_VERIFIED",
    }
    activation_summary = {
        "contract_version": "1.0",
        "production_activation_summary": production_summary,
        "controlled_activation_summary": controlled_summary,
        "controlled_registry_hash": final_state["registry_hash"],
        "controlled_head_event_hash": final_state["head_event_hash"],
        "status": "PASS",
    }
    rollback_summary = {
        "contract_version": "1.0",
        "test_only": True,
        "production_authority": False,
        "rollback_is_pointer_selection_only": True,
        "rdf_reverse_patch_used": False,
        "repository_mutation_by_controller": False,
        "from_publication_id": p1.publication_id,
        "to_publication_id": p0.publication_id,
        "rollback_proposal": workflow["rollback_proposal"],
        "rollback_review_decision": workflow["rollback_review_decision"],
        "rollback_receipt": workflow["rollback_receipt"],
        "generation_sequence": [0, 1, 2],
        "repository_hashes": repository_hashes,
        "publication_tree_hashes": publication_hashes,
        "final_active_publication_id": workflow["resolved_p0"]["active_publication_id"],
        "status": "CONTROLLED_ROLLBACK_VERIFIED",
    }
    security_summary = {
        "contract_version": "1.0",
        "test_only": True,
        "production_authority": False,
        "probe_records": probes,
        "supplemental_probe_records": supplemental_probes,
        "counters": aggregate_probe_records(probes),
        "concurrency_result": race,
        "activation_controller_graphdb_access": [
            "repository_info",
            "export_explicit_nquads",
        ],
        "cleanup": cleanup,
        "status": "PASS",
    }
    return {
        "application-phase06-attestation.json": attestation,
        "activation-summary.json": activation_summary,
        "rollback-summary.json": rollback_summary,
        "authority-binding.json": {
            "contract_version": "1.0",
            **authority.binding,
            "status": "PASS",
        },
        "security-summary.json": security_summary,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    args.expected_commit_sha = (
        args.expected_commit_sha or os.environ.get("GITHUB_SHA") or _git_head()
    )
    _discover_defaults(args)
    required = (
        args.publication_package,
        args.publication_attestation,
        args.phase01_artifact,
        args.phase02_artifact,
        args.phase03_artifact,
        args.phase04_artifact,
        args.phase05_artifact,
        args.expected_commit_sha,
    )
    if not all(required):
        print(
            json.dumps(
                {
                    "status": "LOCAL_VERIFICATION_ENVIRONMENT_BLOCKED",
                    "detail": "exact Stage08--Phase05 physical artifacts are unavailable",
                },
                sort_keys=True,
            )
        )
        return 0
    license_available = any(
        os.environ.get(name)
        for name in (
            "GRAPHDB_LICENSE_FILE",
            "GRAPHDB_LICENSE_CONTENT",
            "GRAPHDB_LICENSE_B64",
        )
    )
    if not license_available:
        print(
            json.dumps(
                {
                    "status": "LOCAL_VERIFICATION_ENVIRONMENT_BLOCKED",
                    "detail": "licensed GraphDB is required for final Phase06 verification",
                },
                sort_keys=True,
            )
        )
        return 0

    authority = load_production_phase06_authority(**_authority_arguments(args))
    production_store = ActivationStateStore(
        Path("runtime_outputs/activation/production") / args.expected_commit_sha,
        lambda: load_production_phase06_authority(**_authority_arguments(args)),
    )
    production_controller = ActivationController(
        production_store,
        ReadOnlyGraphDBTargetVerifier(
            ReadOnlyGraphDBClient(),
            publication_scenario=args.publication_scenario,
        ),
    )
    production_registry, production_pointer = production_controller.initialize()
    production_state = production_controller.status()
    if (
        authority.production_activation_candidate_count != 0
        or production_state["activation_cycles"] != 0
        or production_state["rollback_cycles"] != 0
        or production_state["current_pointer"] != production_pointer
    ):
        raise ValueError("production zero-candidate bootstrap state is not closed")

    controlled_root = (
        Path("runtime_outputs/activation/controlled") / args.expected_commit_sha
    )
    fixture = build_controlled_activation_fixture(controlled_root)
    controlled_authority = fixture["authority"]
    repository_ids = (
        controlled_authority.base_publication.repository_id,
        controlled_authority.activation_candidates[0].repository_id,
    )
    project = ""
    client: GraphDBClient | None = None
    override: Path | None = None
    generated: Path | None = None
    cleanup = {
        "controlled_repository_count": 0,
        "cleanup_failures": 1,
        "status": "PENDING",
    }
    try:
        project, client, override, generated = _start_graphdb(
            controlled_authority.controlled_fixture_hash
        )
        import_package(client, fixture["old"]["graphdb_directory"])
        import_package(client, fixture["new"]["graphdb_directory"])
        live_verifier = ReadOnlyGraphDBTargetVerifier(ReadOnlyGraphDBClient())
        probes: list[dict[str, Any]] = []
        _repository_attack_probes(
            fixture=fixture,
            client=client,
            verifier=live_verifier,
            state_directory=controlled_root / "repository-attacks",
            records=probes,
        )
        p0_package = fixture["old"]["graphdb_directory"]
        p1_package = fixture["new"]["graphdb_directory"]
        repository_hashes = {
            "p0_before": _repository_hash(client, p0_package),
            "p1_before": _repository_hash(client, p1_package),
        }
        publication_hashes = {
            "p0_before": publication_tree_sha256(
                controlled_authority.base_publication.package_directory
            ),
            "p1_before": publication_tree_sha256(
                controlled_authority.activation_candidates[0].package_directory
            ),
        }

        def checkpoint(name: str) -> None:
            repository_hashes[f"p0_{name}"] = _repository_hash(client, p0_package)
            repository_hashes[f"p1_{name}"] = _repository_hash(client, p1_package)

        workflow = run_controlled_activation_workflow(
            fixture=fixture,
            state_directory=controlled_root / "main-state",
            verifier=live_verifier,
            checkpoint=checkpoint,
        )
        publication_hashes.update(
            {
                "p0_after": publication_tree_sha256(
                    controlled_authority.base_publication.package_directory
                ),
                "p1_after": publication_tree_sha256(
                    controlled_authority.activation_candidates[0].package_directory
                ),
            }
        )
        expected_repository_keys = {
            "p0_before",
            "p1_before",
            "p0_after_activation",
            "p1_after_activation",
            "p0_after_rollback",
            "p1_after_rollback",
        }
        if set(repository_hashes) != expected_repository_keys:
            raise ValueError("repository checkpoints are incomplete")
        if not (
            repository_hashes["p0_before"]
            == repository_hashes["p0_after_activation"]
            == repository_hashes["p0_after_rollback"]
            == controlled_authority.base_publication.repository_semantic_hash
            and repository_hashes["p1_before"]
            == repository_hashes["p1_after_activation"]
            == repository_hashes["p1_after_rollback"]
            == controlled_authority.activation_candidates[0].repository_semantic_hash
            and publication_hashes["p0_before"] == publication_hashes["p0_after"]
            and publication_hashes["p1_before"] == publication_hashes["p1_after"]
        ):
            raise ValueError("controlled publication/repository immutability failed")

        review_outcomes = {
            item["decision"]: item["resulting_status"]
            for item in workflow["final_state"]["review_decisions"]
        }
        _review_probe(
            probes,
            details="Explicit human rejection left the controlled pointer unchanged.",
            expected="REJECTED",
            observed=review_outcomes["REJECT"],
        )
        _review_probe(
            probes,
            details="Explicit human deferral left the controlled pointer unchanged.",
            expected="DEFERRED",
            observed=review_outcomes["DEFER"],
        )
        _review_probe(
            probes,
            details="Explicit human approval selected controlled P1.",
            expected="APPROVED_FOR_ACTIVATION",
            observed=workflow["activation_review_decision"]["resulting_status"],
        )
        _review_probe(
            probes,
            details="Explicit human approval selected prior controlled P0.",
            expected="APPROVED_FOR_ACTIVATION",
            observed=workflow["rollback_review_decision"]["resulting_status"],
        )
        supplemental = _non_repository_security_probes(
            fixture=fixture,
            workflow=workflow,
            state_directory=controlled_root / "security",
            records=probes,
        )
        race = run_controlled_process_race(
            fixture=fixture,
            state_directory=controlled_root / "race-state",
        )
        probes.append(
            build_probe_record(
                attack="concurrency",
                expected_code="ACTIVATION_CONCURRENCY_CONFLICT",
                observed_code=(
                    "ACTIVATION_CONCURRENCY_CONFLICT"
                    if race["blocked"] == 1 and race["success"] == 1
                    else "NO_ERROR"
                ),
                blocked=race["blocked"] == 1 and race["success"] == 1,
                details="Ran two processes against the same generation and pointer hash.",
            )
        )

        with TemporaryDirectory(prefix="kg-mnp-phase06-determinism-") as directory:
            replay_fixture = build_controlled_activation_fixture(Path(directory))
            replay = run_controlled_activation_workflow(
                fixture=replay_fixture,
                state_directory=Path(directory) / "state",
                verifier=replay_fixture["offline_verifier"],
            )
        deterministic_fields = (
            "activation_proposal",
            "activation_review_decision",
            "activation_receipt",
            "rollback_proposal",
            "rollback_review_decision",
            "rollback_receipt",
            "final_registry",
            "final_pointer",
        )
        determinism_digests = [
            semantic_hash({field: run[field] for field in deterministic_fields})
            for run in (workflow, replay)
        ]
        determinism_runs = len(determinism_digests)
        determinism_passed = sum(
            digest == determinism_digests[0] for digest in determinism_digests
        )
        if determinism_passed != determinism_runs:
            raise ValueError("controlled Phase06 deterministic reconstruction failed")

        cleanup = _cleanup_graphdb(
            project=project,
            client=client,
            repository_ids=repository_ids,
            override=override,
            generated=generated,
        )
        project = ""
        client = None
        override = None
        generated = None
        (
            production_final_registry,
            production_final_pointer,
            production_final_state,
        ) = production_store.load(
            expected_registry_hash=production_state["registry_hash"],
            expected_head_event_hash=production_state["head_event_hash"],
        )
        production_pointer_unchanged = bool(
            production_registry == production_final_registry
            and production_pointer == production_final_pointer
            and production_final_state["activation_cycles"] == 0
            and production_final_state["rollback_cycles"] == 0
        )
        if not production_pointer_unchanged:
            raise ValueError("production pointer changed during controlled integration")
        documents = _artifact_documents(
            commit_sha=args.expected_commit_sha,
            authority=authority,
            production_initial_registry=production_registry,
            production_initial_pointer=production_pointer,
            production_final_registry=production_final_registry,
            production_final_pointer=production_final_pointer,
            production_final_state=production_final_state,
            fixture=fixture,
            workflow=workflow,
            probes=probes,
            supplemental_probes=supplemental,
            race=race,
            repository_hashes=repository_hashes,
            publication_hashes=publication_hashes,
            cleanup=cleanup,
            determinism_runs=determinism_runs,
            determinism_passed=determinism_passed,
        )
        output = args.artifact_output or (
            Path("runtime_reports/activation") / args.expected_commit_sha
        )
        output.mkdir(parents=True, exist_ok=False)
        for name, value in documents.items():
            _write_json(output / name, value)
        artifact_verification = verify_application_phase06_artifact(
            output,
            **_authority_arguments(args),
            expected_registry_hash=workflow["final_state"]["registry_hash"],
            expected_head_event_hash=workflow["final_state"]["head_event_hash"],
        )
        if (
            artifact_verification["status"]
            != "APPLICATION_PUBLICATION_ACTIVATION_VERIFIED"
        ):
            raise ValueError("independent Phase06 artifact verification failed")
    finally:
        if project and client is not None:
            _cleanup_graphdb(
                project=project,
                client=client,
                repository_ids=repository_ids,
                override=override,
                generated=generated,
            )

    print(
        json.dumps(
            {
                "status": "APPLICATION_PUBLICATION_ACTIVATION_VERIFIED",
                "production_activation_candidates": (
                    authority.production_activation_candidate_count
                ),
                "production_pointer_unchanged": production_pointer_unchanged,
                "controlled_fixture_hash": (
                    controlled_authority.controlled_fixture_hash
                ),
                "generation_sequence": [0, 1, 2],
                "controlled_registry_hash": workflow["final_state"]["registry_hash"],
                "controlled_head_event_hash": workflow["final_state"][
                    "head_event_hash"
                ],
                "artifact_verification_status": artifact_verification["status"],
                "cleanup_status": cleanup["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
