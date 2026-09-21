"""Deterministic external-network replacement, preserving production builders."""
import json

import httpx

from zhigou_toolchain.modeling.delivery.trace import CALL_LINK
from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import ModelLock, QwenClient


class PromptSpy:
    def __init__(self, *, client_type=CompatibleClient, responses=None, **options):
        self.client_type, self.options = client_type, options
        self.responses = iter(responses) if responses is not None else None
        self.requests = []
        self.health_requests = 0

    def handler(self, request):
        if request.method == "GET":
            self.health_requests += 1
            return httpx.Response(200, json={"data": [{"id": "synthetic-model"}]})
        payload = json.loads(request.content)
        link = CALL_LINK.get() or {}
        self.requests.append({"request": payload, "native_agent_run_id": link.get("native_agent_run_id"),
            "method_id": link.get("method_id"), "parent_audit_call_id": link.get("parent_audit_call_id")})
        if self.responses is not None:
            value = next(self.responses)
            if isinstance(value, BaseException):
                raise value
            if isinstance(value, httpx.Response):
                return value
        else:
            # Exact schema keys select fixed synthetic responses. No gold or
            # final graph is read to manufacture model answers.
            schema = payload.get("structured_outputs", {}).get("json")
            if schema is None:
                schema = payload.get("response_format", {}).get("json_schema", {}).get("schema")
            if schema is None:
                schema = json.loads(payload["messages"][0]["content"].split("\nJSON schema: ", 1)[1])
            fields = set(schema.get("properties", {}))
            if fields == {"decisions", "unresolved"}:
                value = {"decisions": [], "unresolved": []}
            elif fields == {"additions", "unresolved"}:
                value = {"additions": [], "unresolved": []}
            elif fields == {"facts", "unresolved"}:
                value = {"facts": [], "unresolved": []}
            elif fields == {"objects", "targets", "exclusions", "unresolved"}:
                value = {"objects": ["Synthetic"], "targets": [], "exclusions": [], "unresolved": []}
            elif fields == {"patches", "unresolved"}:
                context = json.loads(payload["messages"][1]["content"])
                source = next(s for s in context["sources"] if s["quoteable_text"] == "Alpha")
                value = {"patches": [{"draft_ref": "value", "field": "literal", "value": "Alpha",
                    "item_id": source["source_alias"], "quote": "Alpha", "quote_start": 0,
                    "reason": "Fixed synthetic source-grounded correction"}], "unresolved": []}
            else:
                raise AssertionError("Synthetic response must be explicitly specified for this schema")
        return httpx.Response(200, headers={"x-request-id": "mock-http-request"}, json={
            "id": "mock-public-response", "model": "synthetic-model",
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(value)}}]})

    def client(self):
        return self.client_type(ModelLock("synthetic-model", "mock-fixed-v1", "http://localhost/v1"),
            transport=httpx.MockTransport(self.handler), **self.options)


CLIENT_TYPES = (QwenClient, CompatibleClient)
