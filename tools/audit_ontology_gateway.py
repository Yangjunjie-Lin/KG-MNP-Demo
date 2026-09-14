"""Read-only audit of the public gateway implementation implicated by a live overrun."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import httpx

REPO = "jlcodes99/cockpit-tools"
COMMIT = "c4c05a8e1ba590237340919142aad3d82e0dc52d"
PREFIX = "sidecars/cockpit-cliproxy/third_party/CLIProxyAPI/"
FILES = ["internal/translator/codex/openai/responses/codex_openai-responses_request.go",
    "internal/translator/codex/openai/chat-completions/codex_openai_request.go", "internal/registry/models/codex_client_models.json"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    with httpx.Client(timeout=30, trust_env=False) as client:
        for index, path in enumerate(FILES):
            url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{PREFIX}{path}"
            response = client.get(url)
            response.raise_for_status()
            name = f"{index}-" + Path(path).name
            (args.output / name).write_bytes(response.content)
            rows.append({"path": PREFIX + path, "url": url, "file": name, "sha256": hashlib.sha256(response.content).hexdigest()})
    report = {"repository": REPO, "commit": COMMIT, "files": rows,
        "installed_executable_sha256": "424f786f3002010d19b77caff65f8f29e2d2e419128b16a9788cfc0033e78974",
        "binary_to_source_revision_attestation": "NOT_AVAILABLE_PUBLIC_SOURCE_CONSISTENT_WITH_OBSERVED_BEHAVIOR",
        "finding": "CODEX_TRANSLATOR_STRIPS_OUTPUT_TOKEN_LIMIT_FIELDS",
        "live_observation": {"requested_max_completion_tokens": 8192, "reported_completion_tokens": 27832,
            "reported_prompt_tokens": 1312, "reported_total_tokens": 29144},
        "research_action": "PAUSE_ALL_FURTHER_INFERENCE_DO_NOT_WEAKEN_BUDGET_GUARD"}
    (args.output / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
