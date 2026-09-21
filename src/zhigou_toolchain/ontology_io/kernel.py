"""Five-stage task adapter over the shared modeling/semantic kernels.

Unreviewed research drafts only. No scoring import, gold file access, external
retrieval or production approvals. The old primitive pilot is unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from functools import partial
from typing import Any

from rdflib import OWL, RDF

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage import assistance, semantic_check
from zhigou_toolchain.modeling.five_stage.agents import FiveStageCoordinator
from zhigou_toolchain.modeling.five_stage.tools import bind_quote
from zhigou_toolchain.semantic_kernel.shacl import assert_safe_shacl_graph

from .adapters import (
    freeze_task_prediction,
    iri,
    native_exact_key,
    project_task_prediction,
)
from .compilation import compile_task_graphs, freeze_compilation, parse_draft

SYSTEMS = {"TwoAgentKernelV1", "NoRetrieval", "NoConstrainedExtraction", "NoValidationFeedback", "DirectRetrievalContext"}
TEXT = {"type": "string", "minLength": 1, "maxLength": 500}
VOCABULARY = assistance.obj({**{key: {"type": "array", "maxItems": 300, "uniqueItems": True, "items": TEXT}
    for key in ("classes", "entities", "relations")}, "unresolved": assistance.array(TEXT, 30)})
EVIDENCE = assistance.array(assistance.obj({"triple_index": {"type": "integer", "minimum": 0, "maximum": 299},
    "quote": {"type": "string", "minLength": 1, "maxLength": 8192}, "start": {"type": "integer", "minimum": 0}}), 600)


def task_cards(sample):
    labels = {label: "CLASS" for label in sample.supplied_types}
    labels.update({label: "ENTITY" for label in sample.supplied_terms if label not in labels})
    for s, p, o in sample.initial_triples:
        relation = native_exact_key((s, p, o))[1]
        labels.setdefault(s, "CLASS" if relation == "is-a" else "ENTITY")
        labels.setdefault(o, "CLASS" if relation in {"is-a", "instance-of"} else "ENTITY")
        if relation not in {"is-a", "instance-of"}:
            labels.setdefault(p, "OBJECT_PROPERTY")
    for row in sample.allowed_schema.get("entity_types", []):
        labels[row["id"]] = "CLASS"
    for row in sample.allowed_schema.get("relations", []):
        labels[row["id"]] = "OBJECT_PROPERTY"
    return [{"iri": str(iri(label)), "label": label, "element_kind": kind, "aliases": [],
        "definition": "Supplied task input, not reference output"} for label, kind in sorted(labels.items())]


def components(sample, protocol, system):
    if protocol.kernel_profile is None:
        raise ValueError("ABLATION_COMPONENT_NOT_ACTIVE_IN_PARENT_PROFILE" if system.startswith("No") else "KERNEL_PROFILE_CONFIGURATION_REQUIRED")
    profile = protocol.kernel_profile
    parent = {"retrieval": profile.retrieval == "TASK_INPUT_EXACT" and bool(task_cards(sample)),
        "constrained_extraction": profile.constrained_extraction and sample.mode != "CQS_TBOX",
        "validation_feedback": profile.validation_feedback and profile.max_repair_cycles > 0}
    disabled = {"NoRetrieval": "retrieval", "NoConstrainedExtraction": "constrained_extraction", "NoValidationFeedback": "validation_feedback"}.get(system)
    if disabled and not parent[disabled]:
        raise ValueError("ABLATION_COMPONENT_NOT_ACTIVE_IN_PARENT_PROFILE")
    if system == "DirectRetrievalContext" and not parent["retrieval"]:
        raise ValueError("ABLATION_COMPONENT_NOT_ACTIVE_IN_PARENT_PROFILE")
    enabled = {**parent, **({disabled: False} if disabled else {})}
    return {"parent": parent, "enabled": enabled, "ablated_component": disabled,
        "configuration_sha256": semantic_hash({"profile": profile.model_dump(mode="json"), "enabled": enabled}),
        "retrieval_scope": "ONLY_SUPPLIED_INPUT_EXACT_LOOKUP_NO_EXTRA_CORPUS", "additional_external_material": False,
        "quote_binding": "ALWAYS_ON_TEXT_EVIDENCE_INTEGRITY_NOT_ABLATED", "formal_v3_export": False,
        "scope": "TASK_ADAPTED_KERNEL_NOT_FULL_PRODUCTION_TOOLCHAIN",
        "full_ours_claim": False, "native_benchmark_scoring": "SEPARATE_NOT_RUN"}


def _issue(code, target, **extra):
    return {"code": code, "target_stage": target, **extra}


def check_prediction(sample, prediction, vocabulary, evidence, chunks, *, constrained):
    issues, bindings = [], []
    if sample.task_id == "cq2term":
        ids = [row["id"] for row in prediction["cq_terms"]]
        if len(ids) != len(set(ids)) or set(ids) != {row["id"] for row in sample.cq_occurrences}:
            issues.append(_issue("CQ_OCCURRENCE_INVENTORY_MISMATCH", 2))
        return {"issues": issues, "bindings": bindings}
    if sample.task_id == "cq2onto":
        try:
            graph = parse_draft(prediction["turtle"])
            if list(graph.subjects(RDF.type, OWL.NamedIndividual)):
                issues.append(_issue("CQS_ONLY_UNREQUESTED_INDIVIDUALS", 2))
            if any(graph.triples((None, OWL.imports, None))):
                issues.append(_issue("RESEARCH_REMOTE_IMPORT_FORBIDDEN", 2))
        except Exception:  # noqa: BLE001 - invalid model RDF remains a diagnostic, not a silent pass
            issues.append(_issue("OWL_TURTLE_PARSE_FAILED", 2))
        return {"issues": issues, "bindings": bindings}
    triples = prediction["triples"]
    nodes = set(vocabulary["classes"]) | set(vocabulary["entities"])
    relations = set(vocabulary["relations"]) | {"is-a", "instance-of"}
    for index, triple in enumerate(triples):
        if constrained and (triple[0] not in nodes or triple[2] not in nodes or triple[1] not in relations):
            issues.append(_issue("FROZEN_VOCABULARY_VIOLATION", 3, triple_index=index))
        candidates = [row for row in evidence if row["triple_index"] == index]
        found = False
        for row in candidates:
            for chunk in chunks:
                if not chunk["start"] <= row["start"] < chunk["end"]:
                    continue
                try:
                    binding = bind_quote(sample.text, chunk, row["quote"], expected_start=row["start"])
                    bindings.append({"triple_index": index, "triple_sha256": semantic_hash(triple), **binding})
                    found = True
                    break
                except ValueError:
                    continue
        if not found:
            issues.append(_issue("EVIDENCE_QUOTE_UNBOUND", 3, triple_index=index))
    if any(row["triple_index"] >= len(triples) for row in evidence):
        issues.append(_issue("ORPHAN_EVIDENCE_REFERENCE", 3))
    if sample.mode == "SCHEMA_ABOX":
        types = {row["id"] for row in sample.allowed_schema.get("entity_types", [])}
        predicates = {row["id"] for row in sample.allowed_schema.get("relations", [])}
        if len(prediction["schemas"]) != len(triples):
            issues.append(_issue("TYPED_FACT_SCHEMA_BINDING_COUNT_MISMATCH", 3))
        for index, row in enumerate(prediction["schemas"]):
            if row["sub"] not in types or row["obj"] not in types or row["rel"] not in predicates:
                issues.append(_issue("LEGAL_CATEGORY_SCHEMA_VIOLATION", 3, schema_index=index))
            if index < len(triples) and row["rel"] != triples[index][1]:
                issues.append(_issue("TYPED_FACT_SCHEMA_RELATION_MISMATCH", 3, schema_index=index))
    return {"issues": issues, "bindings": bindings, "entailment": "NOT_PROVEN_BY_QUOTE_LOCATION"}


def validate_task(sample, prediction, vocabulary, evidence, chunks, *, constrained, config) -> dict:
    checks = check_prediction(sample, prediction, vocabulary, evidence, chunks, constrained=constrained)
    compilation, semantic = None, None
    blockers = []
    try:
        compilation = compile_task_graphs(sample, prediction)
    except Exception as exc:  # noqa: BLE001 - retain uncompileable prediction and bounded repair history
        checks["issues"].append(_issue("SHARED_COMPILATION_FAILED", 2 if sample.mode == "CQS_TBOX" else 3, error_type=type(exc).__name__))
    try:
        if compilation is not None and sample.task_id != "cq2term":
            semantic = semantic_check.check_research_graphs(tbox=parse_draft(compilation["tbox"]), abox=parse_draft(compilation["abox"]),
                shapes=parse_draft(sample.allowed_shapes_turtle) if sample.allowed_shapes_turtle else None,
                reasoner_jar=config.reasoner_jar, timeout_seconds=config.validation_timeout_seconds)
            if semantic["owl_consistency"]["status"] == "INCONSISTENT":
                checks["issues"].append(_issue("OWL_INCONSISTENT", 2))
            if semantic["shacl"]["status"] == "VIOLATION":
                checks["issues"].append(_issue("SHACL_VIOLATION", 3 if sample.mode != "CQS_TBOX" else 2))
            if semantic["owl_consistency"]["status"] not in {"CONSISTENT", "INCONSISTENT"}:
                blockers.append("OWL_CHECK_" + semantic["owl_consistency"]["status"])
            if semantic["shacl"]["status"] not in {"CONFORMS", "VIOLATION", "NOT_APPLICABLE_NO_LEGAL_SHAPES"}:
                blockers.append("SHACL_CHECK_" + semantic["shacl"]["status"])
    except Exception as exc:  # noqa: BLE001 - infrastructure failures must not trigger model repairs
        blockers.append("VALIDATOR_RUNTIME_" + type(exc).__name__)
    return {**checks, "compilation": compilation, "semantic": semantic, "validation_blockers": blockers,
        "status": "ISSUES" if checks["issues"] else "INCOMPLETE_VALIDATION" if blockers else "CHECKED_NOT_SEMANTIC_ACCURACY"}


def generate_kernel(sample, protocol, system, directory, *, run, ask, instruction, output_schema, audit):
    config = protocol.kernel_profile
    if config is None:
        raise ValueError("KERNEL_PROFILE_CONFIGURATION_REQUIRED")
    active = components(sample, protocol, system)
    audit.update(capabilities=active, history=[], repair_cycles=0)
    data = deepcopy(sample.model_dump(mode="json"))
    input_digest = semantic_hash(data)
    flow = FiveStageCoordinator(run, max_repairs=config.max_repair_cycles)

    def execute(stage, tool, action, inputs, *, finish=True) -> Any:
        value = flow.execute(stage, tool, action, inputs=inputs, parent_digest=flow.parent_digest, finish_stage=finish)
        if semantic_hash(sample.model_dump(mode="json")) != input_digest or semantic_hash(data) != input_digest:
            raise ValueError("KERNEL_FROZEN_INPUT_CHANGED")
        return value

    def scope():
        if sample.allowed_shapes_turtle:
            assert_safe_shacl_graph(parse_draft(sample.allowed_shapes_turtle))
        return {"input_sha256": input_digest, "requirements": sample.requirements, "task": sample.task_id,
            "resources": "TASK_INPUT_ONLY", "approval": "NOT_GRANTED", "s3": "N/A" if sample.mode == "CQS_TBOX" else "TEXT_EXTRACTION"}

    audit["scope"] = execute(1, "scope.validate", scope, data)
    cards = task_cards(sample)
    retrieval = execute(2, "structure.retrieve", lambda: assistance.retrieve_cards([c["label"] for c in cards], cards, mode="LLM_SUBSTITUTE")
        if active["enabled"]["retrieval"] else [], {"cards": cards, "enabled": active["enabled"]["retrieval"]}, finish=False)
    audit["retrieval"] = retrieval
    if system == "DirectRetrievalContext":
        # This system is a direct control, not relabelled as a five-stage run.
        prediction = ask(instruction, {"input": data, "retrieval_context": retrieval}, output_schema)
        return freeze_task_prediction(directory / "artifacts", sample, prediction)
    reuse_ask = lambda task, content, schema: ask(task, content, schema, allowed_iris={c["iri"] for c in cards})
    reuse = execute(2, "structure.design", lambda: assistance.select_reuse(reuse_ask, terms=[c["label"] for c in cards], cards=cards,
        retrieval=retrieval, business_rules=sample.requirements) if cards else
        {"decisions": [], "unresolved": [], "status": "NOT_APPLICABLE_NO_SUPPLIED_ONTOLOGY"},
        {"cards": cards, "retrieval": retrieval}, finish=False)
    audit["reuse"] = reuse
    prediction, evidence, vocabulary, chunks, feedback = None, [], None, [], None
    previous_count = None
    while True:
        if flow.next_stage == 2:
            design_context = {"input": data, "reuse": reuse, "retrieval": retrieval}
            if feedback is not None:
                design_context.update(feedback=feedback, previous=prediction)
            if sample.mode == "CQS_TBOX":
                prediction = execute(2, "structure.design", lambda design_context=design_context: ask(instruction + " Revise only against the supplied task and deterministic feedback, never a reference answer.",
                    design_context, output_schema), design_context)
                audit["design"] = {"mode": "NATIVE_CQ_OUTPUT", "sha256": semantic_hash(prediction)}
            else:
                vocabulary = execute(2, "structure.design", lambda design_context=design_context: ask("Design the source-supported class, entity and relation vocabulary needed for the complete task. "
                    "Reuse supplied terms/types/schema when applicable. Distinguish classes from instances; no approvals. This is a candidate vocabulary, not a reference answer.",
                    design_context, VOCABULARY), design_context)
                audit["design"] = vocabulary
        if flow.next_stage == 3:
            if sample.mode == "CQS_TBOX":
                execute(3, "facts.normalize", lambda: {"status": "NOT_APPLICABLE_CQS_ONLY_NO_INSTANCES"}, {"task": sample.task_id})
            else:
                chunked = execute(3, "text.chunk", lambda: assistance.character_chunks(sample.text, text_id=sample.sample_id,
                    text_version=input_digest, window=8192, overlap=256), {"text_sha256": semantic_hash(sample.text)}, finish=False)
                chunks = chunked["chunks"]
                context = {"input": data, "candidate_vocabulary": vocabulary if active["enabled"]["constrained_extraction"] else None,
                    "extraction_constraints": "CLOSED_CANDIDATE_VOCABULARY" if active["enabled"]["constrained_extraction"] else "UNCONSTRAINED_VOCABULARY",
                    "quote_window_limit": 8192}
                if feedback is not None:
                    context.update(feedback=feedback, previous=prediction)
                schema = assistance.obj({"prediction": output_schema, "evidence": EVIDENCE})
                extracted = execute(3, "facts.repair" if feedback else "text.extract", lambda context=context, schema=schema: ask(instruction +
                    " Return the complete prediction with a verbatim source quote and absolute Unicode start for every triple_index. "
                    "Do not invent support; quotation locates evidence, it does not prove entailment. Never replace a nonempty prediction with an empty result to hide validation errors.", context, schema), context, finish=False)
                prediction, evidence = extracted["prediction"], extracted["evidence"]
                checked = execute(3, "evidence.bind", lambda prediction=prediction, vocabulary=vocabulary, evidence=evidence, chunks=chunks: check_prediction(sample, prediction, vocabulary, evidence, chunks,
                    constrained=active["enabled"]["constrained_extraction"]), {"prediction": prediction, "evidence": evidence})
                audit["evidence"] = checked

        if prediction is None:
            raise ValueError("KERNEL_PREDICTION_MISSING")

        validation = execute(4, "semantic.check", partial(validate_task, sample, prediction, vocabulary, evidence, chunks,
            constrained=active["enabled"]["constrained_extraction"], config=config), prediction)
        count = len(prediction.get("triples", prediction.get("cq_terms", []))) if sample.task_id != "cq2onto" else len(prediction["turtle"].strip())
        if previous_count and count == 0:
            raise ValueError("REPAIR_EMPTY_OUTPUT_REJECTED")
        audit["history"].append({"cycle": flow.repairs, "prediction": deepcopy(prediction), "prediction_sha256": semantic_hash(prediction),
            "validation": deepcopy(validation)})
        audit["validation"] = validation
        if not validation["issues"] or not active["enabled"]["validation_feedback"] or flow.repairs >= config.max_repair_cycles:
            break
        target = min(issue["target_stage"] for issue in validation["issues"])
        flow.repair(target, feedback=validation, parent_digest=flow.parent_digest)
        semantic = validation["semantic"]
        feedback = {"issues": validation["issues"], "source": "DETERMINISTIC_PUBLIC_INPUT_CHECKS_ONLY",
            "owl_status": semantic["owl_consistency"]["status"] if semantic else None,
            "shacl_results": sorted(semantic["shacl"].get("results", []), key=semantic_hash) if semantic else []}
        previous_count = count
        audit["repair_cycles"] = flow.repairs
    compilation = validation["compilation"]
    if compilation is not None:
        audit["compiled_artifacts"] = execute(5, "compile.build", lambda: freeze_compilation(directory / "kernel-artifacts", compilation), compilation, finish=False)
    frozen = execute(5, "compile.build", lambda: freeze_task_prediction(directory / "artifacts", sample, prediction), prediction, finish=False)
    execute(5, "archive.verify", lambda: project_task_prediction(directory / "artifacts", sample), frozen)
    audit["status"] = "GENERATED_WITH_VALIDATION_ISSUES" if validation["issues"] else "KERNEL_EXECUTED_VALIDATION_INCOMPLETE" if validation["validation_blockers"] else "KERNEL_EXECUTED"
    audit["limitations"] = ["NOT_FULL_PRODUCTION_TOOLCHAIN", "EXACT_INPUT_RETRIEVAL_NOT_BGE", "UNICODE_CHUNKING_NOT_MODEL_TOKENIZER",
        "NO_EXPERT_APPROVAL", "NO_OS_ISOLATION_AT_LIBRARY_LEVEL", "QUOTE_LOCATION_NOT_ENTAILMENT", "NATIVE_BENCHMARK_SCORE_NOT_COMPUTED"]
    return frozen
