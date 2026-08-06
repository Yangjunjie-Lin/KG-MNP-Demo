import hashlib
import json

from ._helpers import build


def test_artifact_byte_hashes_match_files(tmp_path):
    directory, _, _ = build(tmp_path)
    manifest = json.loads(directory.joinpath("compilation-manifest.json").read_text(encoding="utf-8"))
    for artifact in manifest["artifact_manifest"]:
        data = directory.joinpath(artifact["relative_path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == artifact["byte_sha256"]
