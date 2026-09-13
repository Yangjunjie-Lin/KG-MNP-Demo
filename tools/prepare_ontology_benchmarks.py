"""Explicit version-locked fetch for audit. Never execute downloaded code.

Generation must not mount this audit directory: it contains scoring resources.
Only prepared, allowlisted task inputs may be passed to the model runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]


def selected(benchmark, path, *, with_data=False):
    if path.lower() in {"readme.md", "license", "usage_instructions.md", "requirements.txt"}:
        return True
    if benchmark == "llms4ol_2026":
        return path in {"2026/README.md", "2026/metrics/graph_similarity.py", "2026/metrics/taxonomy.py"} or with_data and path in {
            "2026/TaskA-Flagship/train_task_a.json", "2026/TaskB-Reuse/train_task_b.json"}
    if benchmark == "cq4oe_0_0_1":
        return path.startswith(("CQ2Onto/scripts/", "CQ2Term/scripts/")) and path.endswith(".py") or with_data and path.startswith((
            "CQ2Term/competency_question/", "CQ2Onto/competency_question/", "CQ2Term/00_gold_standard/", "CQ2Onto/00_gold_standard/"))
    if benchmark == "oskgc":
        return path in {"benchmark/LICENSE", "benchmark/hierarchy.xml", "evaluate.py", "utils/data_processing.py"} or path.startswith("evaluator/") and path.endswith(".py") or with_data and path.startswith(("benchmark/data/", "benchmark/ontology/")) and "Airport" in path
    return path.endswith((".py", ".ipynb")) and "checkpoint" not in path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-data", action="store_true", help="Download public audit datasets, never mount these into generation")
    parser.add_argument("--benchmark", default="all")
    args = parser.parse_args()
    registry = yaml.safe_load((ROOT / "config/ontology_io/benchmark_registry.yaml").read_text(encoding="utf-8"))
    with httpx.Client(timeout=90, follow_redirects=False, trust_env=False) as client:
        for key, config in registry["benchmarks"].items():
            if args.benchmark not in {"all", key}:
                continue
            repo = config["repository"].removeprefix("https://github.com/")
            commit = config["commit"]
            tree = client.get(f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1")
            tree.raise_for_status()
            tree = tree.json()
            if tree.get("truncated"):
                raise ValueError("Incomplete upstream inventory")
            candidates = [row for row in tree["tree"] if row["type"] == "blob" and selected(key, row["path"], with_data=args.with_data)]
            if sum(r.get("size", 0) for r in candidates) > 64_000_000:
                raise ValueError("Explicit download budget exceeded")
            directory = ROOT / "runtime/ontology-io/upstream" / key / commit
            directory.mkdir(parents=True, exist_ok=True)
            records = []
            for row in candidates:
                path = PurePosixPath(row["path"])
                if path.is_absolute() or ".." in path.parts or "\\" in str(path):
                    raise ValueError("Unsafe upstream path")
                response = client.get(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}")
                response.raise_for_status()
                data = response.content
                if len(data) != row["size"] or hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() != row["sha"]:
                    raise ValueError("Upstream Git blob mismatch")
                target = directory / path
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.read_bytes() != data:
                    raise ValueError("Retained upstream bytes changed")
                if not target.exists():
                    target.write_bytes(data)
                records.append({"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "git_blob": row["sha"]})
            manifest = {"benchmark_id": key, "repository": config["repository"], "commit": commit, "files": records,
                "execution_status": "NOT_EXECUTED_AUDIT_ONLY", "generation_access": "DENIED"}
            (directory / "asset-lock.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(json.dumps({"benchmark": key, "files": len(records), "status": "FETCHED_NOT_EXECUTED"}), flush=True)


if __name__ == "__main__":
    main()
