from __future__ import annotations

import json
from pathlib import Path
from time import time
from uuid import uuid4

from .protocol import IntegrationReceipt


class LocalWorkflowOutbox:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def enqueue(self, *, action_definition: dict, project_id: str, release_id: str, payload: dict, idempotency_key: str) -> IntegrationReceipt:
        if not action_definition.get("action_id") or not action_definition.get("input_contract") or not action_definition.get("released_ontology_context"):
            raise ValueError("action definition must bind input contract and released ontology context")
        invocation_id = "invocation_" + uuid4().hex
        request = {"invocation_id": invocation_id, "action_definition": action_definition, "project_id": project_id, "release_id": release_id, "payload": payload, "idempotency_key": idempotency_key, "status": "REQUEST_ENQUEUED", "observed_at": time()}
        path = self.root / f"{invocation_id}.json"
        path.write_text(json.dumps(request, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return IntegrationReceipt(plan_id=invocation_id, status="REQUEST_ENQUEUED", desired_release_id=release_id, last_verification_status="NOT_EXECUTED", details={"invocation_id": invocation_id, "execution_status": "EXTERNAL_EXECUTION_NOT_CONFIGURED"})

    def inspect(self, invocation_id: str) -> dict:
        path = self.root / f"{invocation_id}.json"
        if not path.is_file():
            raise KeyError(invocation_id)
        return json.loads(path.read_bytes())
