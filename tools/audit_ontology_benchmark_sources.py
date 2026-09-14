"""Read-only public resource audit; no inference or downloaded code execution."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import httpx
import yaml

from zhigou_toolchain.ontology_io.cli import load, save, verify_assets

ROOT = Path(__file__).resolve().parents[1]


class PublicText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if not self.hidden and value.strip():
            self.parts.append(value.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    registry = yaml.safe_load((ROOT / "config/ontology_io/benchmark_registry.yaml").read_text(encoding="utf-8"))
    audit = []
    for name, config in registry["benchmarks"].items():
        upstream = ROOT / "runtime/ontology-io/upstream" / name / config["commit"]
        verify_assets(upstream)
        lock = load(upstream / "asset-lock.json")
        files = []
        for row in lock["files"]:
            path = row["path"]
            entry = {"path": path, "sha256": row["sha256"], "bytes": row["bytes"]}
            if path.endswith(".py"):
                tree = ast.parse((upstream / path).read_bytes())
                entry["functions"] = [{"name": n.name, "line": n.lineno} for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                entry["imports"] = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
            if "license" in path.lower():
                entry["notice_start"] = (upstream / path).read_text(encoding="utf-8").splitlines()[:8]
            files.append(entry)
        audit.append({"benchmark": name, "commit": config["commit"], "repository": config["repository"],
            "lock_sha256": hashlib.sha256((upstream / "asset-lock.json").read_bytes()).hexdigest(), "files": files})
    save(args.output / "native-source-audit.json", audit)
    webpages = []
    with httpx.Client(timeout=30, trust_env=False, follow_redirects=True) as client:
        urls = ["https://sites.google.com/view/llms4ol2026", "https://ceur-ws.org/Vol-4041/",
            "https://api.crossref.org/works/10.1007/978-3-031-94575-5_18",
            "https://sites.google.com/view/llms4ol2026/flagship-task", "https://sites.google.com/view/llms4ol2026/reuse-task",
            "https://sites.google.com/view/llms4ol2026/submission"]
        for index, url in enumerate(urls):
            entry = {"url": url, "checked_at": datetime.now(UTC).isoformat()}
            try:
                response = client.get(url)
                response.raise_for_status()
                entry.update(status="FETCHED", sha256=hashlib.sha256(response.content).hexdigest(), bytes=len(response.content))
                if "crossref" in url:
                    data = response.json()["message"]
                    entry["metadata"] = {k: data.get(k) for k in ("title", "container-title", "published", "DOI", "type", "publisher")}
                else:
                    document = PublicText()
                    document.feed(response.text)
                    entry["text"] = "\n".join(document.parts)
                    entry["links"] = document.links
                # Public page bytes retained to substantiate observation date.
                (args.output / f"public-source-{index}.txt").write_bytes(response.content)
            except httpx.HTTPError as exc:
                entry.update(status="UNAVAILABLE", error_type=type(exc).__name__)
            webpages.append(entry)
    save(args.output / "official-web-audit.json", webpages)
    print(json.dumps({"status": "AUDITED_NOT_EVALUATED", "benchmarks": len(audit), "web": [r["status"] for r in webpages]}))


if __name__ == "__main__":
    main()
