"""Single HTTP inference request in a killable credential-bearing process.

No generator/scorer logic. Only the existing configured transport is used.
The parent owns all budget reservations and persistent evidence.
"""
from __future__ import annotations

import json
import sys

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.compatible import (
    CompatibleClient,
    configured_client,
)

from .contracts import Protocol


def main():
    raw = sys.stdin.buffer.read(4_000_001)
    if len(raw) > 4_000_000:
        raise ValueError("TRANSPORT_REQUEST_TOO_LARGE")
    command = json.loads(raw)
    protocol = Protocol.model_validate(command["protocol"])
    request = command["request"]
    client = configured_client()
    try:
        if not isinstance(client, CompatibleClient) or protocol.request_profile is None:
            raise ValueError("TRANSPORT_PROFILE_REQUIRED")
        if (client.lock.model_id != protocol.model_id or client.lock.revision != protocol.declared_revision
                or semantic_hash(client.lock.location) != command["endpoint_sha256"]
                or getattr(client, "reasoning_effort", None) != protocol.reasoning_effort):
            raise ValueError("TRANSPORT_BINDING_CHANGED")
        client.configure_request_profile(**protocol.request_profile.model_dump(mode="json"))
        client.max_output_tokens = protocol.budget.max_output_tokens
        try:
            receipt = client.propose(request["instruction"], request["content"], request["schema"], allowed_iris=request["allowed_iris"])
            reply = {"ok": True, "receipt": receipt}
        except Exception as exc:  # noqa: BLE001 - safe public failure only
            reply = {"ok": False, "error_type": type(exc).__name__, "error_code": "MODEL_CALL_FAILED",
                "public_response": getattr(client, "last_public_response", None), "rejection": getattr(client, "last_rejection", None),
                "transport": getattr(client, "last_transport_error", None)}
        print(json.dumps(reply, ensure_ascii=False), flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
