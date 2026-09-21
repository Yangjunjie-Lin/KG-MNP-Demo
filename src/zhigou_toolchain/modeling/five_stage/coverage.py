"""Read-only method/call reconciliation over original registries and receipts."""
from __future__ import annotations

from zhigou_toolchain.modeling.delivery.exchange_io import require

from .registry import registry

# A tool maps only to the computation it actually encloses, not all methods in
# its stage. Composite old operations remain explicitly OUTER_ONLY.
TOOL_METHOD = {"input.check": "1.1", "data.profile": "1.2", "scope.suggest": "1.3",
    "scope.validate": "1.3", "baseline.load": "2.1", "terminology.build": "2.2",
    "alignment.match": "2.2", "structure.retrieve": "2.2", "structure.rerank": "2.3",
    "structure.design": "2.5", "records.map": "3.1", "identity.resolve": "3.5", "text.chunk": "3.2",
    "text.extract": "3.3", "evidence.bind": "3.4", "facts.normalize": "3.6",
    "facts.repair": "4.3", "integrity.check": "4.1", "semantic.graphs": "4.2",
    "repair.route": "4.3", "compile.plan": "5.1", "compile.build": "5.1", "archive.verify": "5.3",
    "provenance.compile": "5.2", "query.check": "5.4", "archive.export": "5.5", "handoff.export": "5.5"}
HUMAN_METHOD = {"modeling.scope.approve": "1.4", "review.action": "4.4", "review.finalize": "4.5",
    "modeling.handoff.check": "5.4"}
# This is an implementation index, not execution evidence or a new registry.
IMPLEMENTATIONS = {
    "1.1": ("five_stage/profiling.py:check_input", "modeling.profile, modeling.scope.draft, modeling.session.open, modeling.tutorial.seed", "verified input"),
    "1.2": ("five_stage/profiling.py:profile_data", "modeling.profile, modeling.scope.draft, modeling.tutorial.seed", "analysis dependency available"),
    "1.3": ("services/modeling_five_stage.py:execute", "modeling.scope.draft, modeling.scope", "explicit draft or scope input"),
    "1.4": ("services/modeling.py:execute", "modeling.scope.approve", "authenticated scope reviewer"),
    "2.1": ("control_plane/baseline.py:build_baseline_snapshot", "modeling.prepare", "locked domain baseline"),
    "2.2": ("five_stage/assistance.py:retrieve_cards; control_plane/alignment.py:align_terms", "modeling.prepare, modeling.proposal", "BGE_FAISS or explicit exact substitute"),
    "2.3": ("five_stage/tools.py:rerank", "modeling.proposal", "BGE_FAISS + nonempty cards; substitute is not reranker"),
    "2.4": ("five_stage/assistance.py:select_reuse", "modeling.proposal", "model assistance or baseline-reuse-provider"),
    "2.5": ("five_stage/assistance.py:generate", "modeling.proposal", "model assistance round two"),
    "3.1": ("services/modeling.py:_propose", "modeling.proposal", "record mapping or selected provider"),
    "3.2": ("five_stage/tools.py:text_chunks; five_stage/assistance.py:character_chunks", "modeling.proposal", "nonempty text, local tokenizer or Unicode substitute"),
    "3.3": ("five_stage/assistance.py:generate", "modeling.proposal", "one physical request per chunk"),
    "3.4": ("five_stage/tools.py:bind_quote; control_plane/providers/mixed_mapping.py:mixed_mapping_drafts.bind_spans", "modeling.proposal, review.finalize", "returned fact/repair or explicit mixed mapping with quote"),
    "3.5": ("control_plane/providers/mixed_mapping.py:mixed_mapping_drafts.identity; control_plane/providers/record_mapping.py:record_mapping_drafts.resolve_identity", "modeling.proposal, review.finalize", "explicit v1/v2 mapped identities and actual finalization rechecks; manual identities are not recomputed"),
    "3.6": ("control_plane/candidates.py:normalize_candidate_drafts", "modeling.proposal", "provider responses"),
    "4.1": ("services/modeling_semantic.py:execute", "modeling.proposal, modeling.semantic.check", "candidate integrity"),
    "4.2": ("five_stage/semantic_check.py:check_graphs", "modeling.semantic.check", "shared compiler; validators report their own NOT_RUN/errors"),
    "4.3": ("services/modeling_assistance.py:assist; five_stage/assistance.py:repair", "modeling.proposal", "action=REPAIR; S4 routes, S3 patches"),
    "4.4": ("services/modeling.py:_review", "review.action", "authenticated human; not Agent approval"),
    "4.5": ("control_plane/confirmation.py:build_confirmed_package", "review.finalize", "review closure + CAS"),
    "5.1": ("services/compilation.py:execute", "compile.plan, compile.build", "confirmed package"),
    "5.2": ("semantic_kernel/provenance.py:compile_statement_provenance", "compile.build", "real provenance construction; graph digests + manifest"),
    "5.3": ("semantic_kernel/packaging/verifier.py:verify_package", "package.verify, compile.validate, compile.build, package.export, modeling.handoff.check, modeling.handoff.export", "actual archive"),
    "5.4": ("semantic_kernel/validators/competency_questions.py:execute_cq_test_plan; services/handoff.py:execute", "compile.build, modeling.handoff.check", "frozen independent answers/negative plan"),
    "5.5": ("services/compilation.py:execute; services/handoff.py", "package.export, modeling.handoff.export", "authorized export, not receiver acknowledgement"),
}


def implementation_view():
    return [{"method_id": m["method_id"], "name": m["full_name"], "stage_id": m["stage"], "roles": m["roles"],
        "function": IMPLEMENTATIONS[m["method_id"]][0], "operations": IMPLEMENTATIONS[m["method_id"]][1],
        "condition": IMPLEMENTATIONS[m["method_id"]][2],
        "audit_tools": [t for t, mid in TOOL_METHOD.items() if mid == m["method_id"]],
        "implementation_status": "BOUNDARY_INSTRUMENTED",
        "verification_status": "REQUIRES_SELECTED_RUN_EVIDENCE",
        "tests": ["tests/upgrade/test_prompt_audit.py", "tests/upgrade/test_step_audit.py"]}
        for m in registry()["methods"]]


def runtime_view(events, *, native=None, trace=None, parameters=None, step_runs=()):
    """No inferred N/A: absent evidence stays NOT_RUN/OUTER_ONLY."""
    starts = {e["call_id"]: e for e in events if e["phase"] == "BEFORE"}
    ends = {e["call_id"]: e for e in events if e["phase"] == "AFTER"}
    rows = []
    operation = events[0]["binding"].get("operation_id") if events else None
    params = parameters if parameters is not None else events[0]["payload"].get("value") if events else None
    for definition in implementation_view():
        calls = []
        for cid, start in starts.items():
            meta = start["metadata"]
            if meta.get("method_id") != definition["method_id"]:
                continue
            end = ends.get(cid)
            calls.append({"audit_call_id": cid, "kind": meta["kind"], "actor": meta.get("actor"),
                "model_kind": meta.get("model_kind"), "model": meta.get("model"),
                "binding": start["binding"], "parent_audit_call_id": meta.get("parent_audit_call_id"),
                "before": start["event_sha256"], "after": end["event_sha256"] if end else None,
                "input_sha256": start["payload"]["semantic_sha256"],
                "output_sha256": end["payload"]["semantic_sha256"] if end else None,
                "status": end["metadata"].get("status") if end else "INTERRUPTED",
                "content_status": start["payload"]["capture"],
                "model_calls": [c for r in (native or {}).get("records", []) if r.get("audit_call_id") == cid for c in r.get("model_calls", [])],
                "validation": "SEE_RESULT_NOT_IMPLIED_BY_TOOL_SUCCESS"})
        recorded = [c for c in calls if c["kind"] != "MODEL"]
        outer = definition["method_id"] in {"3.5", "5.2"} and any(
            s["metadata"].get("tool_id") == ("records.map" if definition["method_id"] == "3.5" else "compile.build") for s in starts.values())
        not_applicable = not recorded and operation is not None and operation not in definition["operations"].split(", ") and operation not in {"modeling.candidate", "modeling.tutorial.seed"}
        condition = "Selected operation is not this method's entrypoint" if not_applicable else None
        if definition["method_id"] == "2.3" and isinstance(params, dict) and (params.get("model_assistance") or {}).get("retrieval") == "LLM_SUBSTITUTE":
            not_applicable, condition = True, "Actual request configuration retrieval=LLM_SUBSTITUTE, not BGE/FlagReranker"
        if definition["method_id"] == "4.3" and isinstance(params, dict) and (params.get("model_assistance") or {}).get("action", "GENERATE") != "REPAIR":
            not_applicable, condition = True, "Actual request action is not REPAIR"
        rows.append({**definition, "execution_status": "RECORDED" if recorded else "OUTER_ONLY" if outer else "NOT_APPLICABLE" if not_applicable else "NOT_RUN",
            "step_run_refs": [{k: r[k] for k in ("run_id", "job_id", "input_artifact_refs", "output_artifact_refs", "validation_status") if k in r}
                for r in step_runs if r["step_id"] == definition["method_id"]],
            "condition_evidence": {"operation_id": operation, "before_event_sha256": events[0]["event_sha256"]} if not_applicable else None,
            "reason": None if recorded else "No independent method receipt; outer computation is not a method receipt" if outer else condition if not_applicable else "No execution evidence in selected attempt; not inferred from stage or source",
            "calls": calls, "model_status": "CHAT_REQUESTS_RECORDED" if any(c["kind"] == "MODEL" for c in calls) else
                "NON_CHAT_LOCAL_MODEL" if any(c["model_kind"] == "NON_CHAT_LOCAL_MODEL" for c in calls) else "NO_RECORDED_MODEL_CALL"})
    model_boundaries = [s for s in starts.values() if s["metadata"]["kind"] == "MODEL"]
    physical = [s for s in model_boundaries if ends.get(s["call_id"], {}).get("metadata", {}).get("dispatch_status") == "TRANSPORT_ATTEMPTED"]
    unknown_dispatch = [s["call_id"] for s in model_boundaries if ends.get(s["call_id"], {}).get("metadata", {}).get("dispatch_status") is None]
    trace_calls = [e for e in (trace or {}).get("events", []) if e["event"] == "llm_call"]
    observed_physical = max(len(physical), len(trace_calls))
    prompt_complete = (trace is not None and trace["capture_status"] == "COMPLETE" and len(physical) == len(trace_calls)
        and all(c.get("prompt", {}).get("template_status") == "SOURCE_MATCHED" for c in trace_calls))
    legacy = bool(events and "capture_configuration" not in events[0]["binding"])
    return {"format": "zhigou-method-audit/1.0.0", "methods": rows,
        "dimensions": {"steps": "INCOMPLETE_METHOD_GRANULARITY" if any(r["execution_status"] == "OUTER_ONLY" for r in rows) else "RECORDED_BOUNDARIES_ONLY_NOT_EXHAUSTIVENESS_PROOF",
            "prompts": "UNKNOWN_HISTORICAL_CAPTURE" if legacy else "INCOMPLETE_DISPATCH_UNCONFIRMED" if unknown_dispatch else "NOT_APPLICABLE_NO_MODEL_CALL" if not observed_physical else "COMPLETE_CLIENT_CAPTURE" if prompt_complete else "INCOMPLETE_OR_NOT_AUTHORIZED",
            "v2": trace["protocol"]["status"] if trace else "NOT_AVAILABLE_NO_TRACE",
            "receiver": "NOT_CONTACTED", "training": "NOT_CONFIRMED"},
        "physical_requests": observed_physical, "model_metadata_calls": len(model_boundaries), "transport_calls": len(trace_calls),
        "unconfirmed_dispatch_call_ids": unknown_dispatch,
        "independent_call_accounting": "NOT_PROVIDED_RUNTIME_NOT_SELF_PROOF"}


def reconcile_physical_requests(observed, events, trace):
    """Verifier input comes from independent MockTransport spy, not trace counts."""
    from zhigou_toolchain.contracts.canonical import semantic_hash
    model_starts = [e for e in events if e["phase"] == "BEFORE" and e["metadata"]["kind"] == "MODEL"]
    not_sent = {e["call_id"] for e in events if e["phase"] == "AFTER" and e["metadata"].get("dispatch_status") == "NOT_SENT_LOCAL_FAILURE"}
    model_starts = [e for e in model_starts if e["call_id"] not in not_sent]
    requests = [e for e in trace["events"] if e["event"] == "llm_call"]
    require(len(observed) == len(model_starts) == len(requests), "PHYSICAL_CALL_COUNT_MISMATCH")
    require(sorted(semantic_hash(p) for p in observed) == sorted(e["metadata"]["request_sha256"] for e in model_starts)
        == sorted(e["request_sha256"] for e in requests), "PHYSICAL_REQUEST_MISMATCH")
    return {"status": "PASS", "physical_requests": len(observed), "nature": "MOCK_TRANSPORT_INDEPENDENT_SPY"}
