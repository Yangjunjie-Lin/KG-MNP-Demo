"""Snapshot selected PRIMARY research sources, without executing external code."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import distribution
from pathlib import Path

import httpx

SOURCES = {
    "deepeval-custom": "https://deepeval.com/docs/metrics-custom",
    "deepeval-geval": "https://deepeval.com/docs/metrics-llm-evals",
    "deepeval-privacy": "https://deepeval.com/docs/data-privacy",
    "deepeval-benchmarks": "https://deepeval.com/docs/benchmarks-introduction",
    "ragas-factual": "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/factual_correctness/",
    "promptfoo": "https://www.promptfoo.dev/docs/configuration/expected-outputs/",
    "llms4ol-flagship": "https://sites.google.com/view/llms4ol2026/flagship-task",
    "llms4ol-reuse": "https://sites.google.com/view/llms4ol2026/reuse-task",
    "cq4oe-current": "https://oeg-upm.github.io/cq4oe-benchmark/leaderboard/index.html",
    "lettria-paper": "https://ceur-ws.org/Vol-4041/paper3.pdf",
    "oaei": "https://oaei.ontologymatching.org/2026/",
}
REPOSITORIES = {"text2kgbench": "cenguix/Text2KGBench", "scope": "wandugu/paper_scion",
    "ontoeval": "ai4curation/ontoeval", "owl2bench": "kracr/owl2bench"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    with httpx.Client(timeout=30, trust_env=False, follow_redirects=True) as client:
        for name, url in SOURCES.items():
            row = {"name": name, "url": url, "accessed_at": datetime.now(UTC).isoformat()}
            try:
                response = client.get(url)
                response.raise_for_status()
                suffix = ".pdf" if name == "lettria-paper" else ".html"
                filename = name + suffix
                (args.output / filename).write_bytes(response.content)
                row.update(status="FETCHED", file=filename, sha256=hashlib.sha256(response.content).hexdigest())
            except httpx.HTTPError as exc:
                row.update(status="UNAVAILABLE", error_type=type(exc).__name__)
            rows.append(row)
        for name, repo in REPOSITORIES.items():
            row = {"name": name, "repository": "https://github.com/" + repo, "accessed_at": datetime.now(UTC).isoformat()}
            try:
                response = client.get(f"https://api.github.com/repos/{repo}/commits/HEAD")
                response.raise_for_status()
                revision = response.json()["sha"]
                response = client.get(f"https://raw.githubusercontent.com/{repo}/{revision}/README.md")
                response.raise_for_status()
                filename = name + "-README.md"
                (args.output / filename).write_bytes(response.content)
                row.update(status="FETCHED_README_ONLY", commit=revision, file=filename,
                    sha256=hashlib.sha256(response.content).hexdigest(), benchmark_execution="NOT_RUN")
            except httpx.HTTPError as exc:
                row.update(status="UNAVAILABLE", error_type=type(exc).__name__)
            rows.append(row)
    dist = distribution("deepeval")
    local = {}
    for relative in ("__init__.py", "telemetry.py", "metrics/base_metric.py", "config/settings.py", "tracing/internal.py"):
        raw = dist.locate_file("deepeval/" + relative).read_bytes()
        local[relative] = hashlib.sha256(raw).hexdigest()
    manifest = {"source_scope": "PRIMARY_SOURCES_DISCOVERED_BY_WEB_SEARCH_NOT_EXHAUSTIVE_INTERNET", "sources": rows,
        "deepeval_installed_version": dist.version, "deepeval_audited_files": local,
        "upstream_existing_locks": "UNCHANGED", "data_acquisition": "NO_NEW_BENCHMARK_DATA_DOWNLOADED", "model_calls": 0}
    (args.output / "sources.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sources": len(rows), "unavailable": sum(r["status"] == "UNAVAILABLE" for r in rows), "model_calls": 0}))


if __name__ == "__main__":
    main()
