#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "graphdb" / "docker-compose.integration.yml"
SCENARIO = "full-confirmation"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _authorities() -> tuple[dict, ...]:
    from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
    from kg_mnp_demo.modeling.review_policy import load_default_review_policy

    dependencies = load_modeling_dependencies()
    return (
        _json(ROOT / "examples/modeling/inputs/partial-basic.json"),
        _json(ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json"),
        _json(ROOT / f"examples/review/expected-logs/{SCENARIO}.log.json"),
        _json(ROOT / f"examples/review/expected-packages/{SCENARIO}.package.json"),
        dependencies["ontology_baseline"], dependencies["mapping_rules"],
        dependencies["terminology_profile"], dependencies["proposal_policy"],
        load_default_review_policy(),
    )


COMPOSE_FILES: list[Path] = [COMPOSE]


def _compose(project: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    file_args: list[str] = []
    for compose_file in COMPOSE_FILES:
        file_args.extend(["-f", str(compose_file)])
    return subprocess.run(
        ["docker", "compose", "-p", project, *file_args, *args],
        cwd=ROOT, check=check, text=True,
    )


def main() -> int:
    from kg_mnp_demo.compilation.policy import load_compiler_policy
    from kg_mnp_demo.graphdb.attestation import build_import_attestation, write_import_attestation
    from kg_mnp_demo.graphdb.client import GraphDBClient
    from kg_mnp_demo.graphdb.importer import import_package
    from kg_mnp_demo.graphdb.package_builder import build_graphdb_import_package
    from kg_mnp_demo.graphdb.package_validator import validate_graphdb_import_package
    from kg_mnp_demo.graphdb.policy import load_graphdb_policy
    from kg_mnp_demo.graphdb.verifier import verify_imported_repository
    from kg_mnp_demo.graphdb._io import json_bytes

    authorities = _authorities()
    compilation = ROOT / f"examples/compilation/expected/{SCENARIO}"
    built = build_graphdb_import_package(compilation, *authorities, load_compiler_policy())
    digest = built["manifest"]["publication_semantic_hash"]
    project = "kgmnp-" + digest[:12]
    package_dir = ROOT / "runtime_outputs" / "graphdb" / digest
    report_dir = ROOT / "runtime_reports" / "graphdb" / digest
    from kg_mnp_demo.compilation.artifacts import write_artifact_set
    write_artifact_set(package_dir, built["files"], force=True)
    license_file = os.environ.get("GRAPHDB_LICENSE_FILE")
    license_content = os.environ.get("GRAPHDB_LICENSE_CONTENT")
    override_file: Path | None = None
    generated_license_file: Path | None = None
    if license_content and not license_file:
        generated_license_file = ROOT / "runtime_outputs" / "graphdb" / f"{digest}.license"
        license_file = str(generated_license_file)
        generated_license_file.write_text(license_content, encoding="utf-8")
    if license_file:
        license_path = Path(license_file).expanduser().resolve()
        if not license_path.is_file():
            raise RuntimeError("GRAPHDB_LICENSE_FILE does not point to a readable file")
        override_file = ROOT / "runtime_outputs" / "graphdb" / f".compose-license-{digest}.yml"
        override_file.write_text(
            "services:\n  graphdb:\n    volumes:\n"
            f"      - '{license_path.as_posix()}:/opt/graphdb/home/work/graphdb.license:ro'\n",
            encoding="utf-8",
        )
        COMPOSE_FILES.append(override_file)
    else:
        raise RuntimeError(
            "GraphDB 11.4.2 requires an external license; set GRAPHDB_LICENSE_FILE "
            "or GRAPHDB_LICENSE_CONTENT. The license is runtime-only and must not be committed."
        )
    try:
        validate_graphdb_import_package(
            package_dir, compilation_directory=compilation,
            cleaned_partial_data=authorities[0], proposal=authorities[1],
            final_review_decision_log=authorities[2], confirmed_modeling_package=authorities[3],
            ontology_baseline=authorities[4], mapping_rules=authorities[5],
            terminology_profile=authorities[6], proposal_policy=authorities[7],
            review_policy=authorities[8], compiler_policy=load_compiler_policy(),
        )
    except Exception:
        if override_file is not None:
            override_file.unlink(missing_ok=True)
        if generated_license_file is not None:
            generated_license_file.unlink(missing_ok=True)
        raise
    client = GraphDBClient(timeout=10.0, retries=1)
    started_at = None
    imported: dict | None = None
    try:
        _compose(project, "up", "-d")
        deadline = time.monotonic() + 240
        while True:
            try:
                if client.health_check()["healthy"]:
                    break
            except Exception:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("GraphDB did not become healthy within 240 seconds")
            time.sleep(3)
        version = client.version_discovery()
        expected_version = load_graphdb_policy()["graphdb"]["product_version"]
        if expected_version not in json.dumps(version, sort_keys=True):
            raise RuntimeError(
                f"GraphDB product version mismatch: expected {expected_version}, got {version}"
            )
        runtime_dir = report_dir / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "graphdb-version.json").write_bytes(json_bytes(version))
        started_at = __import__("kg_mnp_demo.graphdb.attestation", fromlist=["utc_now"]).utc_now()
        imported = import_package(client, package_dir)
        repository_info = client.inspect_repository(built["manifest"]["repository_id"])
        (runtime_dir / "repository-info.json").write_bytes(json_bytes(repository_info))
        (runtime_dir / "import-response.json").write_bytes(json_bytes(imported))
        verification = verify_imported_repository(client, package_dir, report_directory=report_dir)
        policy = load_graphdb_policy()
        attestation = build_import_attestation(
            source_publication_id=built["manifest"]["publication_id"],
            source_compilation_id=built["manifest"]["source_compilation_id"],
            repository_config_hash=built["manifest"]["repository_config_byte_hash"],
            import_dataset_hash=built["manifest"]["assembled_dataset_byte_hash"],
            export_dataset_hash=verification["export_semantic_hash"],
            expected_graph_count=len(built["manifest"]["named_graphs"]),
            actual_graph_count=len(verification["actual_graph_counts"]),
            expected_quad_count=built["manifest"]["assembled_quad_count"],
            actual_quad_count=verification["actual_quad_count"],
            verification=verification, graphdb_version=version,
            image_digest=policy["graphdb"]["image_digest_amd64"],
            repository_id=built["manifest"]["repository_id"],
            create_status=imported["create_status"], import_status=imported["import_status"],
            started_at=started_at,
        )
        write_import_attestation(report_dir / "graphdb-import-attestation.json", attestation)
        client.delete_generated_repository(built["manifest"]["repository_id"])
        print(json.dumps({"status": "IMPORT_VERIFIED", "publication_id": built["manifest"]["publication_id"], "repository_id": built["manifest"]["repository_id"], "quad_count": verification["actual_quad_count"], "graph_count": len(verification["actual_graph_counts"]), "semantic_hash": verification["export_semantic_hash"]}, sort_keys=True))
        return 0
    finally:
        _compose(project, "down", "-v", "--remove-orphans", check=False)
        if override_file is not None:
            override_file.unlink(missing_ok=True)
        if generated_license_file is not None:
            generated_license_file.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
