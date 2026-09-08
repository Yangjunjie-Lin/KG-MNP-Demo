import json

import pytest

from kg_mnp.compilation.policy import load_compiler_policy
from kg_mnp.graphdb.package_builder import build_graphdb_import_package
from kg_mnp.graphdb.package_validator import (
    GraphDBPackageValidationError,
    validate_graphdb_import_package,
)
from scripts.artifact_fixture import materialize_fixture

from ._helpers import authorities, compilation


def test_rehashed_manifest_attack_is_rejected_by_reconstruction(tmp_path):
    values = authorities()
    package = tmp_path / "package"
    built = build_graphdb_import_package(compilation(), *values, load_compiler_policy())
    materialize_fixture(package, built["files"])
    path = package / "graphdb-import-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["assembled_quad_count"] += 1
    path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with pytest.raises(GraphDBPackageValidationError):
        validate_graphdb_import_package(package, compilation_directory=compilation(), cleaned_partial_data=values[0], proposal=values[1], final_review_decision_log=values[2], confirmed_modeling_package=values[3], ontology_baseline=values[4], mapping_rules=values[5], terminology_profile=values[6], proposal_policy=values[7], review_policy=values[8], compiler_policy=load_compiler_policy())
