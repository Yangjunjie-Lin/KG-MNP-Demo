from kg_mnp_demo.compilation.policy import load_compiler_policy
from kg_mnp_demo.graphdb.package_builder import build_graphdb_import_package
from kg_mnp_demo.graphdb.package_validator import validate_graphdb_import_package

from ._helpers import authorities, compilation


def test_package_rebuilds_and_validates_closed_set(tmp_path):
    values = authorities()
    result = build_graphdb_import_package(compilation(), *values, load_compiler_policy(), output_dir=tmp_path / "package")
    manifest = result["manifest"]
    assert manifest["repository_ruleset"] == "empty"
    assert manifest["assembled_quad_count"] == manifest["tbox_triple_count"] + manifest["stage06_quad_count"]
    assert len(manifest["named_graphs"]) == 13
    validated = validate_graphdb_import_package(tmp_path / "package", compilation_directory=compilation(), cleaned_partial_data=values[0], proposal=values[1], final_review_decision_log=values[2], confirmed_modeling_package=values[3], ontology_baseline=values[4], mapping_rules=values[5], terminology_profile=values[6], proposal_policy=values[7], review_policy=values[8], compiler_policy=load_compiler_policy())
    assert validated["deterministic_reconstruction_match"] is True
