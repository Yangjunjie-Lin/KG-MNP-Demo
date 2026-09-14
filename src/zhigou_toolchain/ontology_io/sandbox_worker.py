"""Gold-free OS-sandbox entry; model calls use JSON-only parent IPC.

No credentials, no network, no scorer/upstream/other-answer mounts. Reuse the
existing generate_sample; do not implement a second generation pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

from .contracts import ModelingInput, Protocol
from .engine import generate_sample
from .provenance import runtime_versions


class IPCClient:
    def __init__(self, protocol):
        self.lock = SimpleNamespace(model_id=protocol.model_id, revision=protocol.declared_revision)
        self.reasoning_effort = protocol.reasoning_effort
        self.last_public_response = None

    def configure_request_profile(self, **kwargs):
        self.request_profile = kwargs  # Parent independently uses frozen protocol, never these values.

    def propose(self, instruction, content, schema, *, allowed_iris=()):
        self.last_public_response = None
        message = {"op": "model", "request": {"instruction": instruction, "content": content,
            "schema": schema, "allowed_iris": sorted(allowed_iris)}}
        print(json.dumps(message, ensure_ascii=False), flush=True)
        raw = sys.stdin.buffer.readline(4_000_001)
        if not raw or len(raw) > 4_000_000:
            raise ValueError("SANDBOX_BROKER_RESPONSE_MISSING_OR_OVERSIZE")
        response = json.loads(raw)
        if not response["ok"]:
            self.last_public_response = response.get("public_response")
            raise RuntimeError("BROKER_MODEL_CALL_FAILED")
        return response["receipt"]


def canary(paths):
    public_read = Path("/input/public-input.txt").read_text() == "PUBLIC_CANARY_INPUT"
    Path("/out/write-check.txt").write_text("PUBLIC_OUTPUT")
    output_write = Path("/out/write-check.txt").read_text() == "PUBLIC_OUTPUT"
    readonly = False
    try:
        Path("/code/forbidden-write-test").write_text("unexpected")
    except OSError:
        readonly = True
    inaccessible = {}
    for path in paths:
        try:
            Path(path).read_bytes()
            inaccessible[path] = False
        except (OSError, ValueError):
            inaccessible[path] = True
    network_denied = []
    for host in ("1.1.1.1", "127.0.0.1"):
        try:
            with socket.create_connection((host, 443), timeout=.2):
                network_denied.append(False)
        except OSError:
            network_denied.append(True)
    env_clean = not any("KEY" in k or "TOKEN" in k or k.startswith("OPENAI_") for k in os.environ)
    return {"op": "canary", "inaccessible": inaccessible, "network_denied": network_denied, "credential_env_empty": env_clean,
        "public_input_readable": public_read, "own_output_writable": output_write, "source_readonly": readonly,
        "network_namespace": os.readlink("/proc/self/ns/net"),
        "cwd": str(Path.cwd()), "runtime": runtime_versions(),
        "passed": all(inaccessible.values()) and all(network_denied) and env_clean and public_read and output_write and readonly}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canary", action="store_true")
    parser.add_argument("--forbidden", nargs="*", default=[])
    args = parser.parse_args()
    if args.canary:
        print(json.dumps(canary(args.forbidden)), flush=True)
        return
    from zhigou_toolchain.semantic_kernel.reasoner import verify_reasoner_bundle
    if sys.platform == "linux":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 ** 3, 4 * 1024 ** 3))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    else:
        raise ValueError("OS_SANDBOX_REQUIRES_LINUX_WORKER")
    verify_reasoner_bundle("/opt/robot.jar")
    job = json.loads(Path("/input/job.json").read_bytes())
    sample = ModelingInput.model_validate(job["sample"])
    protocol = Protocol.model_validate(job["protocol"])
    result = generate_sample(sample, protocol, job["system"], Path("/out/result"), client=IPCClient(protocol), replicate_id=job["replicate_id"])
    print(json.dumps({"op": "done", "status": result["status"], "resources": result["resources"], "runtime": runtime_versions()}), flush=True)


if __name__ == "__main__":
    main()
