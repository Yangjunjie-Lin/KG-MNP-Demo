import json
import pytest

from kg_mnp_demo.compilation.policy import load_compiler_policy
from kg_mnp_demo.graphdb.package_builder import build_graphdb_import_package
from kg_mnp_demo.graphdb.package_validator import GraphDBPackageValidationError, validate_graphdb_import_package
from kg_mnp_demo.graphdb.importer import GraphDBImportError, import_package

from ._helpers import authorities, compilation


class _FakeGraphDB:
    def __init__(self, repositories=None, count=0):
        self.repositories = repositories or []
        self.count = count
        self.created = False
        self.deleted = False
        self.imported = False

    def list_repositories(self):
        return self.repositories

    def create_repository(self, _config):
        self.created = True
        return 201

    def inspect_repository(self, _repository_id):
        return {"params": {"ruleset": {"value": "empty"}}}

    def count_repository_statements(self, _repository_id):
        return self.count

    def import_nquads(self, _repository_id, _data):
        self.imported = True
        return 200

    def delete_generated_repository(self, _repository_id):
        self.deleted = True
        return 204


def _golden_package():
    return compilation().parents[2] / "graphdb" / "expected" / "full-confirmation"


def test_import_refuses_existing_repository_before_create():
    import json

    repository_id = json.loads(
        (_golden_package() / "graphdb-import-manifest.json").read_text(encoding="utf-8")
    )["repository_id"]
    client = _FakeGraphDB(repositories=[repository_id])
    with pytest.raises(GraphDBImportError, match="overwrite"):
        import_package(client, _golden_package())
    assert client.created is False


def test_import_refuses_non_empty_fresh_repository_without_cleanup():
    client = _FakeGraphDB(count=1)
    with pytest.raises(GraphDBImportError, match="not empty"):
        import_package(client, _golden_package())
    assert client.created is True
    assert client.imported is False
    assert client.deleted is False


def test_rehashed_manifest_attack_is_rejected_by_reconstruction(tmp_path):
    values = authorities()
    package = tmp_path / "package"
    build_graphdb_import_package(compilation(), *values, load_compiler_policy(), output_dir=package)
    path = package / "graphdb-import-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["assembled_quad_count"] += 1
    path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with pytest.raises(GraphDBPackageValidationError):
        validate_graphdb_import_package(package, compilation_directory=compilation(), cleaned_partial_data=values[0], proposal=values[1], final_review_decision_log=values[2], confirmed_modeling_package=values[3], ontology_baseline=values[4], mapping_rules=values[5], terminology_profile=values[6], proposal_policy=values[7], review_policy=values[8], compiler_policy=load_compiler_policy())
