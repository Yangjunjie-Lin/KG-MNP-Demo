"""Bounded model assistance: recall, two rounds, quoted facts and local repairs.

All outputs are unapproved CandidateDrafts for the existing control plane.
No acceptance answers are accepted by this interface. Model scores are not
probabilities; the explicit LLM substitute does not run BGE or FAISS.
"""
from __future__ import annotations

from copy import deepcopy

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.control_plane.providers.models import (
    candidate_body,
    candidate_draft,
)

from .tools import (
    ToolBlocked,
    bind_quote,
    merge_recall,
    rerank,
    text_chunks,
    vector_recall,
)


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def array(item, maximum=100):
    return {"type": "array", "items": item, "maxItems": maximum}


STRING = {"type": "string", "maxLength": 4000}
NULL_STRING = {"type": ["string", "null"], "maxLength": 4000}


def character_chunks(text, *, text_id, text_version, window=1200, overlap=120):
    """Explicit substitute: bounded Unicode windows, NOT tokenizer inference."""
    if not 0 <= overlap < window <= 8192:
        raise ToolBlocked("CHUNK_WINDOW_INVALID")
    chunks = []
    for start in range(0, len(text), window - overlap):
        value = {"text_id": text_id, "text_version": text_version, "start": start, "end": min(start + window, len(text)),
                 "text": text[start:start + window], "text_hash": semantic_hash(text)}
        chunks.append({**value, "chunk_id": semantic_hash(value)})
        if value["end"] == len(text):
            break
    return {"chunks": chunks, "method": "UNICODE_WINDOW_SUBSTITUTE", "position_unit": "UNICODE_CODE_POINT_HALF_OPEN"}


def _text(item):
    payload = item["payload"]
    return payload.get("text") if item["item_kind"] == "text-block" else None


def repair_source_text(item):
    if item["item_kind"] == "table-cell":
        return item["payload"].get("value", {}).get("normalized_lexical_value")
    return _text(item)


def _draft(row, index, items, *, prefix="model"):
    refs = row["item_refs"]
    if not refs or not set(refs).issubset(items):
        raise ToolBlocked("MODEL_SOURCE_REFERENCE_INVALID")
    return candidate_draft(draft_ref=f"{prefix}-{index}", draft_kind=row["kind"], candidate_action=row["action"],
        body=candidate_body(**row["body"]), rationale=row["rationale"], kg_ir_item_refs=[items[ref]["item_id"] for ref in refs],
        evidence_refs=sorted({e for ref in refs for e in items[ref]["evidence_refs"]}),
        score_basis="LIVE model proposal, uncalibrated and subject to independent validation and human review")


def generate(client, *, context, initial_drafts, configuration, model_locks=None):
    """Only server-verified modeling context enters generation, never oracles."""
    items = {i["item_id"]: i for i in context["kg_ir_items"]}
    source_aliases = {f"S{n}": item for n, item in enumerate(items.values())}
    if len(items) > 2000:
        raise ToolBlocked("MODEL_ITEM_BUDGET_EXCEEDED")
    model_locks = model_locks or {}
    calls, drafts = [], deepcopy(initial_drafts)
    evidence = {e for i in items.values() for e in i["evidence_refs"]}
    baseline = context["baseline_elements"]
    cards = [{**e, "label": next((l["value"] for l in e.get("labels", [])), e["iri"]),
              "definition": e.get("definition") or "", "aliases": []} for e in baseline]
    allowed = {c["iri"] for c in cards}
    def ask(task, data, schema, iris=None):
        result = client.propose(task, data, schema, allowed_iris=allowed if iris is None else iris, evidence_ids=evidence)
        calls.append(result)
        return result["proposal"]
    terms = context["object_families"]
    retrieval = []
    if configuration["retrieval"] == "BGE_FAISS":
        for term in terms:
            if not cards:
                break
            recall = vector_recall(term, cards, model_locks["embedding"])
            ranking = rerank(term, recall["candidates"], model_locks["reranker"], expected_kind="CLASS")
            retrieval.append({"term": term, "recall": recall, "ranking": ranking, "method": "BGE_FAISS_RERANKER"})
    else:
        for term in terms:
            retrieval.append({"term": term, "exact": merge_recall(term, cards, []), "method": "EXACT_PLUS_LLM_RANKING_SUBSTITUTE"})
    reuse = ask("Round 1: rank supplied ontology cards for each object family; choose REUSE, GAP or UNRESOLVED. "
        "Inspect the complete supplied, verified locked baseline. This local baseline is the reuse source; no external search proof is required. "
        "A retrieval miss is not proof of absence. Give brief evidence-based reasons; "
        "never approve a new term. No vector scores are available in LLM substitute mode.",
        {"object_families": terms, "cards": cards, "retrieval": retrieval, "business_rules": context["business_rules"]},
        obj({"decisions": array(obj({"term": STRING, "decision": {"enum": ["REUSE", "GAP", "UNRESOLVED"]},
            "existing_iri": {"enum": [None, *sorted(allowed)]}, "reason": STRING})), "unresolved": array(STRING)}))
    # Empty gaps from a model cannot authorize namespace growth. Only explicit
    # user configuration from the request supplies this closed list.
    approved = set(configuration.get("approved_new_iris", []))
    namespace = context["default_namespace"]
    if any(not iri.startswith(namespace) or iri in allowed for iri in approved):
        raise ToolBlocked("APPROVED_GAP_NAMESPACE_INVALID")
    body = obj({"candidate_type": {"enum": ["CLASS", "DATA_PROPERTY", "OBJECT_PROPERTY", "SUBCLASS_AXIOM", "DOMAIN_AXIOM", "RANGE_AXIOM",
        "NODE_SHAPE", "PROPERTY_SHAPE", "MIN_COUNT", "MAX_COUNT", "DATATYPE", "CLASS_CONSTRAINT", "NODE_KIND", "IN_VALUES"]},
        "subject_iri": NULL_STRING, "predicate_iri": {"enum": [None, *sorted(allowed | approved)]}, "object_iri": NULL_STRING, "target_iri": NULL_STRING,
        "label": NULL_STRING, "integer_value": {"type": ["integer", "null"], "minimum": 0, "maximum": 100000}, "values": array(STRING)})
    completion = ask("Round 2: critically check the reuse decisions against baseline definitions and rules. "
        "Propose ONLY missing structure or constraints, never duplicate baseline definitions. New IRIs must come from approved_new_iris. "
        "Return additions=[] when none are safely justified. Each addition binds source item_refs and rule_indexes (zero-based). "
        "Use only source aliases S0, S1 etc for item_refs; the server binds them to original immutable evidence. "
        "Do not infer schema constraints from sample values. The supplied baseline domain_refs/range_refs are existing axioms, not gaps. "
        "Inspect existing_drafts as well as the baseline: these are already proposed source-bound records, not missing structure. "
        "Free-text notes and string status values are literals, not new ontology terms requiring their own IRIs. "
        "Only list a remaining unsupported requested requirement in unresolved, not every source value or an already represented rule. "
        "A rule not requested by the business is not an unresolved requirement. No external search is required for local baseline reuse. "
        "For DOMAIN_AXIOM/RANGE_AXIOM/SUBCLASS_AXIOM: subject_iri is the property/subclass, object_iri is its target, predicate_iri=null. "
        "For SHACL: subject_iri is a shape, predicate_iri is a direct business-property path or null, never an RDF/RDFS/SHACL metapredicate. "
        "Hard rules may not be removed or weakened. Arbitrary rule equivalence is NOT proven; list unsupported rules explicitly. "
        "candidate_action is CREATE_NEW for new classes/properties, CONSTRAIN for shapes. Return brief reasons, not hidden reasoning.",
        {"round_one": reuse, "baseline": cards, "existing_drafts": drafts, "business_rules": context["business_rules"], "approved_new_iris": sorted(approved),
         "sources": [{"item_ref": alias, "payload": i["payload"]} for alias, i in source_aliases.items()]},
        obj({"additions": array(obj({"kind": {"enum": ["TBOX", "SHACL"]}, "action": {"enum": ["CREATE_NEW", "CONSTRAIN", "REUSE_EXISTING"]},
            "body": body, "item_refs": array({"enum": list(source_aliases)}), "rule_indexes": array({"type": "integer", "minimum": 0}), "rationale": STRING})),
            "unresolved": array(STRING)}), allowed | approved)
    reserved = ("http://www.w3.org/2001/XMLSchema#", "http://www.w3.org/ns/shacl#", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    for index, row in enumerate(completion["additions"]):
        if any(n >= len(context["business_rules"]) for n in row["rule_indexes"]):
            raise ToolBlocked("MODEL_RULE_REFERENCE_INVALID")
        if row["kind"] == "SHACL" and not row["rule_indexes"]:
            raise ToolBlocked("MODEL_RULE_SUPPORT_REQUIRED")
        for key in ("subject_iri", "predicate_iri", "object_iri", "target_iri"):
            iri = row["body"].get(key)
            if iri and iri not in allowed | approved and not iri.startswith(reserved):
                raise ToolBlocked("MODEL_UNAPPROVED_STRUCTURE_IRI")
        if row["body"]["candidate_type"] in {"CLASS", "DATA_PROPERTY", "OBJECT_PROPERTY"} and row["body"]["target_iri"] not in approved:
            raise ToolBlocked("MODEL_BASELINE_REDEFINITION")
        drafts.append(_draft(row, index, source_aliases))
    # Identity comes from deterministic mapping or explicit input drafts. The
    # model cannot mint an identity from a name or invent an unresolved target.
    subjects = {d["body"]["subject_iri"] for d in drafts if d["body"]["candidate_type"] == "INDIVIDUAL"}
    predicates = {e["iri"] for e in baseline if e["element_kind"] in {"DATA_PROPERTY", "OBJECT_PROPERTY"}}
    predicates |= {d["body"]["target_iri"] for d in drafts if d["body"]["candidate_type"] in {"DATA_PROPERTY", "OBJECT_PROPERTY"}}
    chunks_report, facts = [], []
    for item in items.values():
        text = _text(item)
        if not text:
            continue
        chunk_args = {"text_id": item["item_id"], "text_version": semantic_hash(item)}
        chunks = text_chunks(text, lock=model_locks["tokenizer"], **chunk_args) if configuration["chunking"] == "LOCAL_TOKENIZER" else character_chunks(text, **chunk_args)
        chunks_report.append(chunks)
        if sum(len(c["chunks"]) for c in chunks_report) > 32:
            raise ToolBlocked("MODEL_CHUNK_BUDGET_EXCEEDED")
        for chunk in chunks["chunks"]:
            extracted = ask("Extract only explicitly stated facts using supplied subject and predicate IRIs. "
                "Preserve negation and uncertainty as NEGATED/UNKNOWN, never assert them as positive facts. "
                "subject_iri and object_iri (if present) must be supplied identities, otherwise return unresolved. "
                "literal values must occur verbatim inside the quote. quote_start is absolute Unicode offset in the source. "
                "Return facts=[] when no supported fact fits. No new identity, rule or schema.",
                {"chunk": chunk, "subjects": sorted(subjects), "predicates": sorted(predicates), "existing_facts": drafts,
                 "business_rules": context["business_rules"]},
                obj({"facts": array(obj({"subject_iri": {"enum": sorted(subjects)} if subjects else {"type": "string", "maxLength": 0},
                    "predicate_iri": {"enum": sorted(predicates)} if predicates else {"type": "string", "maxLength": 0}, "object_iri": {"enum": [None, *sorted(subjects)]},
                    "literal_value": NULL_STRING, "quote": STRING, "quote_start": {"type": "integer", "minimum": 0},
                    "polarity": {"enum": ["ASSERTED", "NEGATED", "UNKNOWN"]}, "reason": STRING})), "unresolved": array(STRING)}), predicates)
            facts.append({"chunk_id": chunk["chunk_id"], "unresolved": extracted["unresolved"], "facts": []})
            for fact in extracted["facts"]:
                binding = bind_quote(text, chunk, fact["quote"], expected_start=fact["quote_start"])
                if fact["subject_iri"] not in subjects or fact["predicate_iri"] not in predicates:
                    raise ToolBlocked("MODEL_UNKNOWN_IDENTITY_OR_PREDICATE")
                if (fact["object_iri"] is None) == (fact["literal_value"] is None):
                    raise ToolBlocked("MODEL_FACT_VALUE_INVALID")
                if fact["object_iri"] is not None and fact["object_iri"] not in subjects:
                    raise ToolBlocked("MODEL_UNKNOWN_RELATION_TARGET")
                if fact["literal_value"] is not None and (not fact["literal_value"] or fact["literal_value"] not in fact["quote"]):
                    raise ToolBlocked("MODEL_LITERAL_NOT_IN_QUOTE")
                facts[-1]["facts"].append({**fact, "binding": binding, "evidence_refs": item["evidence_refs"]})
                if fact["polarity"] != "ASSERTED":
                    continue
                values = {"candidate_type": "OBJECT_PROPERTY_ASSERTION" if fact["object_iri"] else "DATA_PROPERTY_ASSERTION",
                          "subject_iri": fact["subject_iri"], "predicate_iri": fact["predicate_iri"], "object_iri": fact["object_iri"]}
                if fact["literal_value"] is not None:
                    values["literal"] = {"lexical_value": fact["literal_value"], "datatype_iri": "http://www.w3.org/2001/XMLSchema#string", "language": None}
                drafts.append(_draft({"kind": "ABOX", "action": "ASSERT", "body": values,
                    "item_refs": [item["item_id"]], "rationale": fact["reason"]}, len(drafts), items, prefix="extracted"))
    return drafts, {"execution_source": "LIVE" if all(c["execution_source"] == "LIVE" for c in calls) else "RECORDED", "authority": "PROPOSAL_ONLY", "configuration": configuration,
        "deterministic_input_drafts": {"count": len(initial_drafts), "digest": semantic_hash(initial_drafts), "unchanged": drafts[:len(initial_drafts)] == initial_drafts},
        "model_added_draft_count": len(drafts) - len(initial_drafts),
        "retrieval": retrieval, "round_one": reuse, "round_two": completion, "chunks": chunks_report,
        "extraction": facts, "calls": calls, "independent_answers_accessible": False,
        "rule_equivalence": "HUMAN_REVIEW_REQUIRED", "unresolved": reuse["unresolved"] + completion["unresolved"]}


def repair(client, *, original_drafts, context, issues, configuration):
    """Whitelist replacement of source-grounded ABox values; never patch rules."""
    items = {i["item_id"]: i for i in context["kg_ir_items"]}
    aliases = {f"S{n}": item for n, item in enumerate(items.values())}
    schema = obj({"patches": array(obj({"draft_ref": STRING, "field": {"enum": ["literal", "object_iri"]},
        "value": STRING, "item_id": {"enum": list(aliases)}, "quote": STRING, "quote_start": {"type": "integer", "minimum": 0}, "reason": STRING})), "unresolved": array(STRING)})
    response = client.propose("Propose minimal local ABox repairs for the reported issues using exact source evidence. "
        "Also independently compare ABox values against their bound sources even when structural prevalidation passes. "
        "Human-review pending is workflow status, not a repairable data defect; the server enforces human review after this proposal. "
        "Inspect all existing drafts, including SHACL/NODE_KIND declarations, before declaring a business rule unsupported. "
        "unresolved contains only defects that still remain after the proposed patches; do not copy already satisfied business rules into it. "
        "Only replace literal lexical value or relation target; never remove candidates or edit identities, hard rules, "
        "schema, source data or test answers. Keep UNKNOWN unresolved. An unchanged proposal is not a repair. "
        "item_id must be the short source alias S0/S1/etc. quote and quote_start must refer to quoteable_text ONLY, "
        "not JSON serialization or a whole table row. For a complete cell value quote_start=0.",
        {"drafts": original_drafts, "issues": issues, "sources": [{**item, "source_alias": alias, "quoteable_text": repair_source_text(item)} for alias, item in aliases.items()], "business_rules": context["business_rules"]}, schema)
    drafts, changed, seen = deepcopy(original_drafts), [], set()
    subjects = {d["body"]["subject_iri"] for d in drafts if d["body"]["candidate_type"] == "INDIVIDUAL"}
    by_ref = {d["draft_ref"]: d for d in drafts}
    for patch in response["proposal"]["patches"]:
        draft = by_ref.get(patch["draft_ref"])
        if not draft or draft["draft_kind"] != "ABOX" or patch["draft_ref"] in seen:
            raise ToolBlocked("REPAIR_TARGET_NOT_WHITELISTED")
        seen.add(patch["draft_ref"])
        item = aliases.get(patch["item_id"])
        text = repair_source_text(item) if item else None
        if not text:
            raise ToolBlocked("REPAIR_TEXT_SOURCE_REQUIRED")
        chunk = {"text_id": item["item_id"], "text_version": semantic_hash(item), "start": 0, "end": len(text), "text": text, "text_hash": semantic_hash(text)}
        binding = bind_quote(text, chunk, patch["quote"], expected_start=patch["quote_start"])
        before = deepcopy(draft)
        if patch["field"] == "literal":
            if draft["body"]["candidate_type"] != "DATA_PROPERTY_ASSERTION" or not patch["value"] or patch["value"] not in patch["quote"]:
                raise ToolBlocked("REPAIR_LITERAL_NOT_GROUNDED")
            draft["body"]["literal"]["lexical_value"] = patch["value"]
        else:
            if draft["body"]["candidate_type"] != "OBJECT_PROPERTY_ASSERTION" or patch["value"] not in subjects:
                raise ToolBlocked("REPAIR_RELATION_TARGET_INVALID")
            draft["body"]["object_iri"] = patch["value"]
        if draft["body"] == before["body"]:
            raise ToolBlocked("REPAIR_NO_CHANGE")
        draft["kg_ir_item_refs"] = sorted(set(draft["kg_ir_item_refs"]) | {item["item_id"]})
        draft["evidence_refs"] = sorted(set(draft["evidence_refs"]) | set(item["evidence_refs"]))
        draft["rationale"] = patch["reason"]
        changed.append({"before": before, "after": deepcopy(draft), "binding": binding})
    if not changed:
        raise ToolBlocked("NO_SAFE_REPAIR")
    return drafts, {"execution_source": response["execution_source"], "authority": "PROPOSAL_ONLY", "calls": [response],
        "configuration": configuration, "changes": changed, "unresolved": response["proposal"]["unresolved"],
        "independent_answers_accessible": False, "required_next_steps": ["NEW_CANDIDATE_VERSION", "SEMANTIC_CHECKS", "HUMAN_REVIEW", "FREEZE"]}
