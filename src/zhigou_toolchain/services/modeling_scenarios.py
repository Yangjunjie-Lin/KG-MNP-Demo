"""Scene selection and provider adaptation inside the original session/CAS."""
from __future__ import annotations

from copy import deepcopy

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.ingestion.source_store import SourceStore
from zhigou_toolchain.modeling.control_plane.providers.mixed_mapping import (
    input_inventory,
)
from zhigou_toolchain.modeling.control_plane.providers.models import (
    candidate_body,
    candidate_draft,
)
from zhigou_toolchain.modeling.control_plane.service import ModelingWorkspaceService
from zhigou_toolchain.modeling.five_stage.scenarios import (
    earliest_change,
    frozen_scene,
    require_current,
    resolve,
)

from . import modeling_sessions
from .errors import ServiceBoundaryError


def effective(session):
    return (session or {}).get("scenario", {}).get("effective")


def selected_tables(configuration, stage):
    scene = frozen_scene(configuration)
    caps = configuration["stages"][stage]["selected_capabilities"]
    return [{**t, "literals": {k: v for k, v in t["literals"].items() if v["capability"] in caps}}
            for t in scene["tables"] if t["capability"] in caps]


def source_names(root, datasets):
    store = SourceStore(root)
    identifiers = {s for d in datasets for s in store.load_batch(d["source_batch_id"])["sources"]}
    return {s: store.verify_source(s)["original_name"] for s in identifiers}


def inspect_inputs(configuration, datasets, names):
    inventory = input_inventory(datasets)
    gaps, tables = [], {}
    required_caps = set(configuration["hard_requirements"]["required_capabilities"])
    cells = [i for d in datasets for i in d["items"] if i["item_kind"] == "table-cell"]
    registered = {t["source_name"]: t for t in frozen_scene(configuration)["tables"]}
    for table in inventory["tables"]:
        name = names.get(table["source_id"])
        spec = registered.get(name)
        if spec is None:
            gaps.append({"code": "SCENARIO_UNSUPPORTED_SOURCE", "source": name, "required": False, "support": "NOT_IMPLEMENTED"})
            continue
        allowed = {spec["id_field"], *spec["literals"], *(r["field"] for r in spec["references"])}
        unknown = {h["name"] for h in table["headers"]} - allowed
        if unknown:
            gaps.append({"code": "SCENARIO_UNREGISTERED_FIELD", "source": name, "fields": sorted(unknown), "required": False, "support": "NOT_IMPLEMENTED"})
    table_items = {item for table in inventory["tables"] for item in table["item_ids"]}
    if set(inventory["data_item_ids"]) - table_items:
        gaps.append({"code": "SCENARIO_UNSUPPORTED_SOURCE", "required": False, "support": "DECLARED_TABLES_ONLY"})
    for spec in selected_tables(configuration, "S2"):
        matches = [t for t in inventory["tables"] if names.get(t["source_id"]) == spec["source_name"]]
        fields = {spec["id_field"], *spec["literals"], *(r["field"] for r in spec["references"])}
        if len(matches) != 1:
            gaps.append({"code": "SCENARIO_SOURCE_MISSING_OR_AMBIGUOUS", "source": spec["source_name"],
                         "capability": spec["capability"], "required": spec["capability"] in required_caps})
            continue
        table = matches[0]
        if not any(i["payload"]["row"] > 1 and i["item_id"] in table["item_ids"] for i in cells):
            gaps.append({"code": "SCENARIO_SELECTED_TABLE_HAS_NO_RECORDS", "source": spec["source_name"],
                "capability": spec["capability"], "required": spec["capability"] in required_caps})
        missing = fields - {h["name"] for h in table["headers"]}
        for field in sorted(missing):
            cap = spec["literals"].get(field, {}).get("capability", spec["capability"])
            gaps.append({"code": "SCENARIO_FIELDS_MISSING", "source": spec["source_name"], "fields": [field],
                         "capability": cap, "required": cap in required_caps})
        tables[spec["record_id"]] = table
    return {"gaps": gaps, "tables": tables, "status": "BLOCKED" if gaps else "AVAILABLE"}


def preview(app, project, selection, run_id=None):
    from .sources import verified_run
    try:
        configuration = resolve(selection)
    except ValueError as exc:
        raise ServiceBoundaryError("SCENARIO_SELECTION_INVALID", str(exc), status_code=422) from exc
    modeling = ModelingWorkspaceService(project.root)
    wanted = configuration["domain_pack"]
    compatible = any(r["pack_id"] == wanted["pack_id"] and r["pack_version"] == wanted["pack_version"]
                     for r in modeling.project_lock["resolved_domain_packs"])
    session = modeling_sessions.read(project.root)
    run_id = run_id or (session or {}).get("frozen", {}).get("run_id")
    inputs = {"status": "NOT_RUN_NO_INPUT", "gaps": [], "tables": {}}
    if run_id:
        dataset = verified_run(project.root, run_id).dataset
        inputs = inspect_inputs(configuration, [dataset], source_names(project.root, [dataset]))
    return {"effective": configuration, "project_compatible": compatible, "inputs": inputs,
        "earliest_affected_stage": earliest_change(effective(session), configuration),
        "status": "AVAILABLE" if compatible and inputs["status"] == "AVAILABLE" else "BLOCKED",
        "model_calls": 0, "authority": "READ_ONLY_PREVIEW_NOT_CONFIRMATION"}


def install(session, configuration, principal):
    from .modeling_expert import initial_state
    old = effective(session)
    start = earliest_change(old, configuration)
    if old == configuration:
        return
    if start is None:
        start = 5  # Provenance-only selection change refreshes the delivery view.
    history = deepcopy(session.get("scenario", {}).get("history", []))
    if old:
        history.append({k: deepcopy(v) for k, v in session["scenario"].items() if k != "history"})
    session["scenario"] = {"version": session.get("scenario", {}).get("version", 0) + 1,
        "effective": configuration, "selected_by": principal.principal_id, "history": history}
    if not session.get("expert", {}).get("enabled"):
        session["expert"] = initial_state()
    state = session["expert"]
    for stage in range(start, 6):
        key = str(stage)
        previous = state["stages"][key]
        state["history"].append(deepcopy(previous))
        version = deepcopy(previous)
        config = version["configuration"]
        config["coverage_confirmed"] = False
        prior_bound_criterion = criterion(old, stage) if old else None
        config["criteria"] = [c for c in config["criteria"] if c != prior_bound_criterion]
        new_bound_criterion = criterion(configuration, stage)
        if any(c["criterion_id"] == new_bound_criterion["criterion_id"] for c in config["criteria"]):
            raise ServiceBoundaryError("SCENARIO_CRITERION_NAMESPACE_CONFLICT", "Rename the conflicting human checkpoint explicitly; it will not be silently replaced", status_code=409)
        config["criteria"].append(new_bound_criterion)
        version.update(version=previous["version"] + 1, status="DRAFT", confirmed_by=None, confirmed_at=None,
            author=principal.principal_id, scenario_stage_digest=configuration["stage_digests"][f"S{stage}"])
        version.pop("digest", None)
        version["digest"] = semantic_hash(version)
        state["stages"][key] = version
    checks = deepcopy(session["checks"])
    modeling_sessions.invalidate(session, start, "Scenario Prompt preset changed; preserve expert text and reconfirm affected versions")
    if start == 5:
        session["checks"] = checks  # Presentation does not invalidate unchanged semantic checks.


def criterion(configuration, stage):
    options = configuration["stages"][f"S{stage}"]
    return {"criterion_id": options["criterion_id"], "description": options["expert_additions"]["post_review"],
        "required": True, "source": "scene-resource:" + configuration["resource_digest"]}


def execute(app, project, request, principal):
    params = request.parameters
    if request.operation_id == "modeling.scenario.preview":
        return preview(app, project, params["selection"], params.get("run_id"))
    session = modeling_sessions.read(project.root)
    if not session or session["revision"] != params["expected_revision"]:
        raise ServiceBoundaryError("SESSION_HEAD_CONFLICT", "Reload the scenario session", status_code=409)
    if request.operation_id == "modeling.scenario.quality":
        from rdflib import Graph

        from zhigou_toolchain.modeling.five_stage.scenario_quality import evaluate

        from .compilation import package_location
        from .modeling_expert import require_package
        require_package(session, params["package_id"])
        if not effective(session):
            raise ServiceBoundaryError("SCENARIO_REQUIRED", "No frozen scene to evaluate", status_code=409)
        from zhigou_toolchain.semantic_kernel.packaging.archive import (
            read_verified_package_files,
        )
        archive = package_location(project, params["package_id"])
        files, _ = read_verified_package_files(archive, expected_package_id=params["package_id"])
        graph = Graph().parse(data=files["data/abox.ttl"].decode("utf-8"), format="turtle")
        report = evaluate(graph, session["frozen"].get("scenario_acceptance"), effective(session))
        bound = {"package_id": params["package_id"], "configuration_digest": effective(session)["digest"],
            "label_digest": semantic_hash(session["frozen"].get("scenario_acceptance")), "metrics": report,
            "independence": "SESSION_FROZEN_BEFORE_PROPOSAL", "human_approval": "NOT_GRANTED"}
        session["scenario_quality"] = bound
        session["revision"] += 1
        modeling_sessions.save(project.root, session)
        return {"scenario_quality": bound}
    if principal.principal_type != "HUMAN" or not principal.can("scope:approve"):
        raise ServiceBoundaryError("HUMAN_CONFIGURATION_REQUIRED", "Scene selection requires authenticated scope authority", status_code=403)
    view = preview(app, project, params["selection"])
    if view["status"] != "AVAILABLE":
        raise ServiceBoundaryError("SCENARIO_CONFIGURATION_BLOCKED", "Inspect scene conflicts, missing sources and locked project dependencies", status_code=422)
    install(session, view["effective"], principal)
    modeling_sessions.save(project.root, session)
    return {"session": session, "scenario_preview": view}


def require_active(session):
    try:
        require_current(effective(session))
    except ValueError as exc:
        raise ServiceBoundaryError("SCENARIO_PRESET_MIGRATION_REQUIRED", "Select and save a current scene Prompt preset, then reconfirm and regenerate from S1; historical records are unchanged", status_code=409) from exc


def require_confirmation(session, stage):
    require_active(session)
    configuration = effective(session)
    if not configuration:
        return
    version = session.get("expert", {}).get("stages", {}).get(str(stage), {})
    if version.get("status") != "CONFIRMED" or version.get("scenario_stage_digest") != configuration["stage_digests"][f"S{stage}"]:
        raise ServiceBoundaryError("SCENARIO_CONFIRMATION_REQUIRED", "Confirm expert criteria for this exact resolved scene configuration", status_code=409)


def scope_parameters(root, params):
    configuration = effective(modeling_sessions.read(root))
    if not configuration:
        return params
    require_confirmation(modeling_sessions.read(root), 1)
    expected = configuration["stages"]["S1"]["enabled_object_families"]
    if set(params["object_families"]) != set(expected) or params["namespace"] != configuration["namespace"]:
        raise ServiceBoundaryError("SCENARIO_SCOPE_MISMATCH", "Scope must use the previewed object families and namespace", status_code=422)
    options = configuration["stages"]["S1"]
    scene = frozen_scene(configuration)
    required = ["SCENE_CAPABILITY:" + cap for cap in options["selected_capabilities"]]
    required.extend("DECLARED_FIELD:" + field for field in options["declared_fields"])
    required.extend("IDENTITY_SPACE:" + table["record_id"] + "/" + table["id_field"] for table in selected_tables(configuration, "S1"))
    required.extend("POLICY:" + name + ":" + value for name, value in sorted(scene["rules"].items()))
    return {**params, "in_scope": sorted(set(params["in_scope"]) | set(required)),
        "out_of_scope": params.get("out_of_scope", [])}


def mapping_for(root, datasets, baseline, questions):
    """Resolve data-only scene fields to the existing evidence mapping provider."""
    configuration = effective(modeling_sessions.read(root))
    if not configuration:
        return None
    names = source_names(root, datasets)
    inspected = inspect_inputs(configuration, datasets, names)
    if inspected["status"] != "AVAILABLE":
        raise ServiceBoundaryError("SCENARIO_INPUTS_INCOMPLETE", "Selected scene capabilities need their real sources", status_code=422)
    tables = []
    for spec in selected_tables(configuration, "S3"):
        found = inspected["tables"][spec["record_id"]]
        tables.append({"record_id": spec["record_id"], "source_id": found["source_id"], "locator": found["locator"],
            "identity_space": spec["record_id"], "class_iri": spec["class_iri"], "id_field": spec["id_field"],
            "literals": {k: {"predicate_iri": r["predicate_iri"], "datatype": r["datatype"]} for k, r in spec["literals"].items()},
            "references": spec["references"]})
    # Fixed source adapter: no detail-dependent omission of registered fields.
    scene = frozen_scene(configuration)
    specifications = {s["source_name"]: s for s in scene["tables"]}
    actual_tables = input_inventory(datasets)["tables"]
    data_item_ids = set(input_inventory(datasets)["data_item_ids"])
    fields_by_source = {t["source_id"]: {h["column"]: h["name"] for h in t["headers"]} for t in actual_tables}
    selected_by_name = {names[t["source_id"]]: t for t in tables}
    exclusions = []
    for data in datasets:
        for item in data["items"]:
            if item["item_kind"] != "table-cell":
                if item["item_id"] in data_item_ids:
                    raise ServiceBoundaryError("SCENARIO_UNSUPPORTED_SOURCE", "This scene's current input contract is declared tables only", status_code=422)
                continue  # Verified document/table containers are not fact cells.
            if item["payload"]["row"] == 1:
                continue
            source = item["source_ids"][0]
            name = names[source]
            spec = specifications.get(name)
            field = fields_by_source[source][item["payload"]["column"]]
            if spec is None or field not in {spec["id_field"], *spec["literals"], *(r["field"] for r in spec["references"])}:
                raise ServiceBoundaryError("SCENARIO_UNREGISTERED_FIELD", "Explicitly extend the versioned scene contract before using unknown fields", status_code=422)
            selected = selected_by_name.get(name)
            if selected is None or field not in {selected["id_field"], *selected["literals"], *(r["field"] for r in selected["references"])}:
                raise ServiceBoundaryError("SCENARIO_MAPPING_INCOMPLETE", "Every declared source field must remain mapped", status_code=422)
    # Prepare source-backed vocabulary through the original candidate mechanism.
    terms, supports = {}, {}
    for spec in selected_tables(configuration, "S2"):
        terms[spec["class_iri"]] = "CLASS"
        supports[spec["class_iri"]] = (spec["source_name"], spec["id_field"])
        for field, item in spec["literals"].items():
            terms[item["predicate_iri"]] = "DATA_PROPERTY"
            supports[item["predicate_iri"]] = (spec["source_name"], field)
        for item in spec["references"]:
            terms[item["predicate_iri"]] = "OBJECT_PROPERTY"
            supports[item["predicate_iri"]] = (spec["source_name"], item["field"])
    existing = {e["iri"]: e for e in baseline["elements"]}
    declarations = []
    for iri, kind in sorted(terms.items()):
        if iri in existing:
            continue
        support_name, support_field = supports[iri]
        item = next(i for d in datasets for i in d["items"] if i["item_kind"] == "table-cell" and i["payload"]["row"] == 1
            and names[i["source_ids"][0]] == support_name and i["payload"]["value"]["normalized_lexical_value"] == support_field)
        declarations.append(candidate_draft(draft_ref="scene-term-" + semantic_hash(iri)[:20], draft_kind="TBOX", candidate_action="CREATE_NEW",
            body=candidate_body(candidate_type=kind, target_iri=iri, label=iri.rsplit(":", 1)[-1]),
            kg_ir_item_refs=[item["item_id"]], evidence_refs=item["evidence_refs"], competency_question_refs=questions,
            rationale="Explicit unapproved scene vocabulary design; frozen resource " + configuration["resource_digest"] + "; original human review required"))
    return {"configuration": configuration, "rules": {"profile": "evidence-record-mapping-v2", "tables": tables, "exclusions": exclusions},
            "declarations": declarations, "selected_terms": sorted(terms)}
