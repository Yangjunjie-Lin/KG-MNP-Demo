"""Independent synthetic transport for a scene S4→S2 label-only correction."""
import json

import httpx

from tests.upgrade.expert_spy import ExpertSpy


def expand(value):
    nodes, layouts = value["nodes"], value["layouts"]
    def decode(v):
        if isinstance(v, dict):
            if set(v) == {"$ref"}:
                return decode(nodes[v["$ref"]])
            if set(v) == {"$object"}:
                keys, values = v["$object"]
                return {k: decode(child) for k, child in zip(layouts[keys], values, strict=True)}
            return {k: decode(child) for k, child in v.items()}
        return [decode(child) for child in v] if isinstance(v, list) else v
    return decode(value["root"])


class ScenarioRepairSpy(ExpertSpy):
    def __init__(self):
        super().__init__()
        self.target = None
        self.source = None

    def transport(self, request):
        if request.method != "POST":
            return super().transport(request)
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])
        binding, data = context["expert_binding"], context["task_context"]
        if binding["purpose"] == "REVISE" and self.target:
            self.requests.append(payload)
            source_text = data["sources"][self.source]["text"]
            proposal = {"base_digest": data["base_digest"], "unresolved": [], "changes": [{"target": self.target,
                "field": "label", "value": source_text, "issue_id": "synthetic-scene-label", "evidence_ref": self.source,
                "quote": source_text, "quote_start": 0}]}
            self.revised = True
            return httpx.Response(200, json={"id": "mock-scene-revision", "model": "synthetic-expert",
                "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(proposal)}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}})
        response = super().transport(request)
        if binding["purpose"] == "REVIEW" and data["artifact"]["tool_id"] == "semantic.graphs" and not self.revised:
            targets = expand(data["material"])["allowed_patch_targets"]["targets"]
            self.target, target = next((key, value) for key, value in targets.items() if "label" in value.get("editable_fields", {})
                and value["editable_fields"]["label"]["value"] != data["sources"][value["source_item_refs"][0]]["text"])
            self.source = target["source_item_refs"][0]
            body = response.json()
            proposal = json.loads(body["choices"][0]["message"]["content"])
            proposal["decision"] = "REVISE"
            proposal["checks"][0]["status"] = "FAIL"
            proposal["issues"] = [{"issue_id": "synthetic-scene-label", "criterion_id": proposal["checks"][0]["criterion_id"],
                "severity": "BLOCKING", "location": self.target + ".body.label", "description": "Use the original field spelling for this synthetic vocabulary label",
                "suggestion": "Change only this editable label", "evidence_refs": [self.source], "target_stage": 2}]
            body["choices"][0]["message"]["content"] = json.dumps(proposal)
            return httpx.Response(200, json=body)
        return response
