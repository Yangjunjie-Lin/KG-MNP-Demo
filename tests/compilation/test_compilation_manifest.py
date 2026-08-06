import json

from ._helpers import build


def test_manifest_contains_closed_artifact_metadata(tmp_path):
    directory, manifest, _ = build(tmp_path)
    loaded = json.loads(directory.joinpath("compilation-manifest.json").read_text(encoding="utf-8"))
    assert loaded["release_status"] == "FORMALLY_VALIDATED"
    assert loaded["compilation_id"].startswith("urn:kg-mnp:compilation:")
    assert all("byte_sha256" in item and "semantic_sha256" in item for item in loaded["artifact_manifest"])
