"""Independent HTTP witness with explicitly synthetic expert responses."""
import json

import httpx

from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import ModelLock, QwenClient


class ExpertSpy:
    def __init__(self, *, qwen=False, revise_scope=False, response_mode="PASS", revise_stage=None):
        self.qwen = qwen
        self.requests = []
        self.revise_scope = revise_scope
        self.response_mode = response_mode
        self.revised = False
        self.revise_stage = revise_stage

    def transport(self, request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "synthetic-expert"}]})
        value = json.loads(request.content)
        self.requests.append(value)
        context = json.loads(value["messages"][1]["content"])
        binding = context["expert_binding"]
        data = context["task_context"]
        if binding["purpose"] == "REVIEW":
            ref = next(r for r in data["evidence"] if r.startswith("output:"))
            response = {"decision": self.response_mode, "summary": "SYNTHETIC MockTransport review, not a human judgment", "issues": [],
                        "checks": [{"criterion_id": c["criterion_id"], "status": "PASS", "reason": "Synthetic check",
                                    "evidence_refs": [ref]} for c in context["mandatory_criteria"]]}
            if self.revise_scope and not self.revised and data["artifact"]["tool_id"] == "scope.validate":
                response["decision"] = "REVISE"
                response["checks"][0]["status"] = "FAIL"
                response["issues"] = [{"issue_id": "synthetic-scope-description", "criterion_id": response["checks"][0]["criterion_id"],
                    "severity": "BLOCKING", "location": "scope.domain_description", "description": "Use the frozen rule wording",
                    "suggestion": "Update only the scope description", "evidence_refs": ["rule:0"], "target_stage": 1}]
            target_tool = {2:"structure.design", 3:"facts.normalize", 4:"semantic.graphs", 5:"compile.plan"}.get(self.revise_stage)
            if target_tool and not self.revised and data["artifact"]["tool_id"] == target_tool:
                source_ref = next(k for k, v in data["sources"].items() if v["text"] == "Alpha")
                response["decision"] = "REVISE"
                response["checks"][0]["status"] = "FAIL"
                response["issues"] = [{"issue_id":"synthetic-local-revision", "criterion_id":response["checks"][0]["criterion_id"],
                    "severity":"BLOCKING", "location":{2:"class.body.label",3:"value.body.literal.lexical_value",4:"value.body.literal.lexical_value",5:"plan.package_name"}[self.revise_stage], "description":"Synthetic source-bound local correction",
                    "suggestion":"Use source text Alpha", "evidence_refs":[source_ref], "target_stage":3 if self.revise_stage == 4 else self.revise_stage}]
        elif binding["purpose"] == "REVISE":
            source_ref = data["issues"][0]["evidence_refs"][0]
            text = data["sources"][source_ref]["text"]
            target, field = {2:("class","label"),3:("value","literal"),4:("value","literal"),5:("plan","package_name")}.get(self.revise_stage,("scope","description"))
            response = {"base_digest": data["base_digest"], "unresolved": [], "changes": [{"target": "scope",
                "field": "description", "value": text, "issue_id": data["issues"][0]["issue_id"],
                "evidence_ref": source_ref, "quote": text, "quote_start": 0}]}
            response["changes"][0].update(target=target, field=field)
            if self.revise_stage == 5:
                response["changes"][0]["value"] = text.lower()
            self.revised = True
        else:
            raise AssertionError("Generation requires a purpose-specific synthetic fixture")
        return httpx.Response(200, json={"id": f"mock-{len(self.requests)}", "model": "synthetic-expert",
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(response)}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}})

    def client(self):
        kind = QwenClient if self.qwen else CompatibleClient
        return kind(ModelLock("synthetic-expert", "mock-v1", "https://synthetic.invalid/v1"),
                    transport=httpx.MockTransport(self.transport))
