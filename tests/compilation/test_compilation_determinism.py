import json

from kg_mnp_demo.compilation.compiler import build_artifact_set
from ._helpers import authorities
from ._helpers import build


def test_same_authorities_have_same_compilation_bytes(tmp_path):
    one, m1, _ = build(tmp_path / "one")
    two, m2, _ = build(tmp_path / "two")
    assert m1["compilation_id"] == m2["compilation_id"]
    for relative in ("rdf/abox.nt", "rdf/dataset.nq", "rdf/modeling-provenance.nt", "rdf/review-audit.nt", "shacl/report.json", "reasoner/owl-consistency-report.json", "compilation-manifest.json"):
        assert one.joinpath(relative).read_bytes() == two.joinpath(relative).read_bytes()


def _reverse_keys(value):
    if isinstance(value, dict):
        return {key: _reverse_keys(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse_keys(item) for item in value]
    return value


def test_json_key_order_and_crlf_inputs_do_not_change_compilation_bytes():
    values = authorities()
    baseline_files, baseline_manifest = build_artifact_set(*values)
    reordered = tuple(
        json.loads(
            json.dumps(_reverse_keys(value), ensure_ascii=False, indent=2).replace("\n", "\r\n")
        )
        for value in values
    )
    reordered_files, reordered_manifest = build_artifact_set(*reordered)

    assert baseline_manifest["compilation_id"] == reordered_manifest["compilation_id"]
    assert baseline_files == reordered_files
