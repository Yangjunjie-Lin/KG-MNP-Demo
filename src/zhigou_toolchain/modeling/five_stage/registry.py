"""One packaged method registry shared by the API, UI and teaching reader."""
from __future__ import annotations

import json
from importlib.resources import files

from zhigou_toolchain.contracts.canonical import semantic_hash


def resource_root():
    return files(__package__).joinpath("resources")


def registry() -> dict:
    value = json.loads(resource_root().joinpath("method-registry.v1.json").read_bytes())
    source = json.loads(resource_root().joinpath(value["source_ref"]).read_bytes())
    value["source_manifest"] = {
        "profile": "KG-MNP Canonical JSON v1", "content_hash": semantic_hash(source),
        "meaning": "Method identity, not execution or approval evidence",
    }
    return value


def tutorial_files() -> dict[str, bytes]:
    """Only this packaged, non-executable allowlist is downloadable."""
    root = resource_root().joinpath("tutorial")
    result = {}
    for directory in ("input", "stages", "output", "output/queries", "output/tests", "anomaly"):
        node = root.joinpath(directory)
        if node.is_dir():
            for item in node.iterdir():
                if item.is_file() and item.name.rsplit(".", 1)[-1] in {"json", "jsonl", "ttl", "rq", "txt"}:
                    result[directory + "/" + item.name] = item.read_bytes()
    return result


def tutorial() -> dict:
    content = tutorial_files()
    return {"schema_version": "1.0.0", "execution_source": "TUTORIAL_FIXTURE",
            "execution_status": "NOT_RUN", "review_status": "PENDING",
            "notice": "合成教学参考。评分不是模型执行结果；假定确认快照不是审批凭证。",
            "files": {name: json.loads(raw) if name.endswith(".json") else raw.decode("utf-8")
                      for name, raw in content.items()}}
