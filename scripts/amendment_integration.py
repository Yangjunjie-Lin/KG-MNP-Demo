#!/usr/bin/env python3
"""Licensed Phase 05 integration entry point."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from kg_mnp_demo.amendment.attestation import build_phase05_attestation
from kg_mnp_demo.amendment.authority_binding import load_production_phase05_authority
from kg_mnp_demo.amendment.errors import AmendmentError, AmendmentErrorCode
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

if __package__:
    from scripts import graphdb_integration as graphdb_runtime
    from scripts.amendment_controlled_fixture import (
        build_controlled_publication_pair,
        run_controlled_republication_harness,
    )
else:
    import graphdb_integration as graphdb_runtime  # type: ignore[import-not-found]
    from amendment_controlled_fixture import (  # type: ignore[import-not-found]
        build_controlled_publication_pair,
        run_controlled_republication_harness,
    )


def _verify_live_graphdb(
    *,
    evidence: dict,
    old: dict,
    new: dict,
) -> dict[str, str]:
    from kg_mnp_demo.graphdb.client import GraphDBClient, GraphDBClientError
    from kg_mnp_demo.graphdb.importer import import_package
    from kg_mnp_demo.graphdb.verifier import verify_imported_repository

    digest = evidence["controlled_fixture_hash"]
    project = "kgmnp-amendment-" + digest[:12]
    license_path, source_type = graphdb_runtime._license_runtime_file(digest)
    generated = license_path if source_type in {"CONTENT", "B64"} else None
    override: Path | None = None
    client = GraphDBClient(timeout=10.0, retries=1)
    repository_ids = (
        old["graphdb_manifest"]["repository_id"],
        new["graphdb_manifest"]["repository_id"],
    )
    if repository_ids[0] == repository_ids[1]:
        raise ValueError(
            "controlled re-publication reused the base repository identity"
        )
    try:
        if license_path is not None:
            override = (
                Path("runtime_outputs/amendment") / f".compose-license-{digest}.yml"
            ).resolve()
            override.parent.mkdir(parents=True, exist_ok=True)
            override.write_text(
                "services:\n  graphdb:\n    volumes:\n"
                f"      - '{license_path.as_posix()}:/opt/graphdb/home/conf/graphdb.license:ro'\n",
                encoding="utf-8",
            )
            graphdb_runtime.COMPOSE_FILES.append(override)
        graphdb_runtime._compose(project, "up", "-d")
        deadline = time.monotonic() + 240
        while True:
            try:
                if client.health_check()["healthy"]:
                    break
            except (GraphDBClientError, OSError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("GraphDB did not become healthy within 240 seconds")
            time.sleep(3)
        import_package(client, old["graphdb_directory"])
        old_before = verify_imported_repository(client, old["graphdb_directory"])
        import_package(client, new["graphdb_directory"])
        new_actual = verify_imported_repository(client, new["graphdb_directory"])
        old_after = verify_imported_repository(client, old["graphdb_directory"])
        result = {
            "old_repository_before_hash": old_before["export_semantic_hash"],
            "old_repository_after_hash": old_after["export_semantic_hash"],
            "new_repository_expected_hash": new["graphdb_manifest"][
                "assembled_dataset_semantic_hash"
            ],
            "new_repository_actual_hash": new_actual["export_semantic_hash"],
        }
        if not (
            result["old_repository_before_hash"]
            == result["old_repository_after_hash"]
            == old["graphdb_manifest"]["assembled_dataset_semantic_hash"]
            and result["new_repository_expected_hash"]
            == result["new_repository_actual_hash"]
        ):
            raise ValueError(
                "live GraphDB immutable re-publication verification failed"
            )
        return result
    finally:
        for repository_id in reversed(repository_ids):
            try:
                client.delete_generated_repository(repository_id)
            except (GraphDBClientError, OSError, ValueError):
                pass
        graphdb_runtime._compose(project, "down", "-v", "--remove-orphans", check=False)
        graphdb_runtime._cleanup_license_runtime_files(override, generated)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage08-artifact", type=Path)
    parser.add_argument("--publication-attestation", type=Path)
    parser.add_argument("--phase01-artifact", type=Path)
    parser.add_argument("--phase02-artifact", type=Path)
    parser.add_argument("--phase03-artifact", type=Path)
    parser.add_argument("--phase04-artifact", type=Path)
    parser.add_argument("--expected-commit-sha")
    parser.add_argument("--publication-scenario", default="full-confirmation")
    parser.add_argument("--artifact-output", type=Path)
    args = parser.parse_args()
    if not args.expected_commit_sha:
        args.expected_commit_sha = os.environ.get("GITHUB_SHA")
    if not all(
        (
            args.stage08_artifact,
            args.phase01_artifact,
            args.phase02_artifact,
            args.phase03_artifact,
            args.phase04_artifact,
        )
    ):
        stage08 = Path("runtime_outputs/publication") / args.publication_scenario
        manifest_path = stage08 / "publication-manifest.json"
        if manifest_path.is_file():
            try:
                publication_hash = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )["publication_semantic_hash"]
                args.stage08_artifact = stage08
                args.publication_attestation = (
                    Path("runtime_reports/publication")
                    / publication_hash
                    / "publication-attestation.json"
                )
                args.phase01_artifact = (
                    Path("runtime_reports/application") / publication_hash
                )
                args.phase02_artifact = (
                    Path("runtime_reports/workbench") / publication_hash
                )
                args.phase03_artifact = (
                    Path("runtime_reports/diagnostics") / publication_hash
                )
                phase04_reports = sorted(
                    Path("runtime_reports/governance").glob(
                        "**/application-phase04-attestation.json"
                    )
                )
                if phase04_reports:
                    args.phase04_artifact = phase04_reports[-1].parent
            except (OSError, KeyError, TypeError, json.JSONDecodeError):
                pass
    values = {
        "stage08_artifact": args.stage08_artifact,
        "phase01_artifact": args.phase01_artifact,
        "phase02_artifact": args.phase02_artifact,
        "phase03_artifact": args.phase03_artifact,
        "phase04_artifact": args.phase04_artifact,
        "publication_attestation": args.publication_attestation,
    }
    if (
        not all(
            values[key]
            for key in (
                "stage08_artifact",
                "phase01_artifact",
                "phase02_artifact",
                "phase03_artifact",
                "phase04_artifact",
            )
        )
        or not args.expected_commit_sha
    ):
        print(
            json.dumps(
                {
                    "status": "LOCAL_VERIFICATION_ENVIRONMENT_BLOCKED",
                    "detail": "licensed exact Stage08--Phase04 artifacts were not supplied",
                },
                sort_keys=True,
            )
        )
        return 0
    try:
        authority = load_production_phase05_authority(
            **values,
            expected_commit_sha=args.expected_commit_sha,
            publication_scenario=args.publication_scenario,
        )
    except (AmendmentError, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "detail": str(exc)}, sort_keys=True))
        return 2
    license_available = any(
        os.environ.get(name)
        for name in (
            "GRAPHDB_LICENSE_FILE",
            "GRAPHDB_LICENSE_CONTENT",
            "GRAPHDB_LICENSE_B64",
        )
    )
    if license_available:
        controlled_root = (
            Path("runtime_outputs/amendment/controlled") / args.expected_commit_sha
        )
        evidence, old, new = build_controlled_publication_pair(controlled_root)
        evidence.update(_verify_live_graphdb(evidence=evidence, old=old, new=new))
    else:
        evidence = run_controlled_republication_harness()
    deterministic_replay = run_controlled_republication_harness()
    if canonical_json_bytes(evidence) != canonical_json_bytes(deterministic_replay):
        raise ValueError("controlled re-entry/re-publication determinism failure")
    if args.artifact_output is None and os.environ.get("GITHUB_SHA"):
        args.artifact_output = (
            Path("runtime_reports/amendment") / args.expected_commit_sha
        )
    security = dict(evidence["security"])
    security["unauthorized_amendment_attempts"] += 1
    try:
        authority.require_request(
            "urn:kg-mnp:test-fixture:phase05:approved-amendment-request:unapproved"
        )
    except AmendmentError as exc:
        if exc.code != AmendmentErrorCode.UNAPPROVED_AMENDMENT:
            raise
        security["unauthorized_amendment_blocked"] += 1
    else:
        raise ValueError("out-of-scope production amendment was not blocked")
    if args.artifact_output:
        output = args.artifact_output
        output.mkdir(parents=True, exist_ok=True)
        intake = {
            "contract_version": "1.0",
            "fixture_type": "PHASE05_CONTROLLED_AMENDMENT_FIXTURE",
            "test_only": True,
            "production_authority": False,
            "controlled_fixture_hash": evidence["controlled_fixture_hash"],
            "controlled_amendment_type": evidence["controlled_amendment_type"],
            "intake_id": evidence["intake_id"],
            "intake_manifest_hash": evidence["intake_manifest_hash"],
            "approved_amendment_request_id": evidence["approved_amendment_request_id"],
            "base_cleaned_data_hash": evidence["base_cleaned_data_hash"],
            "revised_cleaned_data_hash": evidence["revised_cleaned_data_hash"],
            "declared_json_diff": evidence["declared_json_diff"],
            "actual_json_diff": evidence["actual_json_diff"],
            "status": "PASS",
        }
        republication = {
            "contract_version": "1.0",
            "test_only": True,
            "production_authority": False,
            "controlled_reentry_cycles": 1,
            "controlled_republication_cycles": 1,
            "review_reject_no_publication": evidence["review_reject_no_publication"],
            "review_defer_no_publication": evidence["review_defer_no_publication"],
            "old_publication_immutable": evidence[
                "old_publication_package_before_sha256"
            ]
            == evidence["old_publication_package_after_sha256"],
            "old_repository_immutable": evidence["old_graphdb_package_before_sha256"]
            == evidence["old_graphdb_package_after_sha256"],
            "old_publication_package_before_sha256": evidence[
                "old_publication_package_before_sha256"
            ],
            "old_publication_package_after_sha256": evidence[
                "old_publication_package_after_sha256"
            ],
            "old_graphdb_package_before_sha256": evidence[
                "old_graphdb_package_before_sha256"
            ],
            "old_graphdb_package_after_sha256": evidence[
                "old_graphdb_package_after_sha256"
            ],
            "old_repository_id": evidence["old_repository_id"],
            "new_repository_id": evidence["new_repository_id"],
            "old_modeling_proposal_hash": evidence["old_modeling_proposal_hash"],
            "new_modeling_proposal_hash": evidence["new_modeling_proposal_hash"],
            "new_review_decision_log_hash": evidence["new_review_decision_log_hash"],
            "new_confirmed_modeling_package_hash": evidence[
                "new_confirmed_modeling_package_hash"
            ],
            "old_phase03_diagnostic_package_hash": evidence[
                "old_phase03_diagnostic_package_hash"
            ],
            "new_phase03_diagnostic_package_hash": evidence[
                "new_phase03_diagnostic_package_hash"
            ],
            "amendment_lineage": evidence["amendment_lineage"],
            "governance_provenance_separate_from_business_evidence": evidence[
                "governance_provenance_separate_from_business_evidence"
            ],
            **{
                key: evidence[key]
                for key in (
                    "old_tbox_hash",
                    "new_tbox_hash",
                    "old_shacl_hash",
                    "new_shacl_hash",
                    "old_abox_hash",
                    "new_abox_hash",
                    "old_publication_hash",
                    "new_publication_hash",
                    "old_webvowl_hash",
                    "new_webvowl_hash",
                )
            },
            "target_diagnostic_before": evidence["target_diagnostic_before"],
            "target_diagnostic_after": evidence["target_diagnostic_after"],
            "status": "PASS",
        }
        attestation = build_phase05_attestation(
            commit_sha=args.expected_commit_sha,
            upstream_phase04_attestation_sha256=authority.phase04_attestation_sha256,
            upstream_phase04_workspace_hash=authority.phase04_workspace_hash,
            production_pending_amendments=authority.production_pending_amendments,
            controlled_fixture_hash=evidence["controlled_fixture_hash"],
            controlled_reentry_cycles=1,
            controlled_republication_cycles=1,
            security=security,
            determinism_runs=2,
            determinism_passed=2,
            hashes={
                key: evidence[key]
                for key in (
                    "old_tbox_hash",
                    "new_tbox_hash",
                    "old_shacl_hash",
                    "new_shacl_hash",
                    "old_abox_hash",
                    "new_abox_hash",
                    "old_publication_hash",
                    "new_publication_hash",
                    "old_webvowl_hash",
                    "new_webvowl_hash",
                    "old_repository_before_hash",
                    "old_repository_after_hash",
                    "new_repository_expected_hash",
                    "new_repository_actual_hash",
                )
            },
            diagnostics={
                "before": republication["target_diagnostic_before"],
                "after": republication["target_diagnostic_after"],
            },
        )
        documents = {
            "application-phase05-attestation.json": attestation,
            "amendment-intake-summary.json": intake,
            "republication-summary.json": republication,
            "authority-binding.json": {
                "contract_version": "1.0",
                **authority.binding,
                "status": "PASS",
            },
            "security-summary.json": {
                "contract_version": "1.0",
                "test_only": True,
                "production_authority": False,
                **security,
                "status": "PASS",
            },
        }
        for name, value in documents.items():
            (output / name).write_bytes(canonical_json_bytes(value) + b"\n")
    print(
        json.dumps(
            {
                "status": "APPLICATION_AMENDMENT_REPUBLICATION_VERIFIED",
                "production_pending_amendments": authority.production_pending_amendments,
                "production_reentry_cycles": 0,
                "production_new_publications": 0,
                "controlled_fixture_hash": evidence["controlled_fixture_hash"],
                "artifact_output": str(args.artifact_output)
                if args.artifact_output
                else None,
                "notice": "production zero-amendment state is valid; controlled harness is test-only",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
