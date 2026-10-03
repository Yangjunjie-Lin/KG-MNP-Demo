"""Scene Prompt presets keep original authority, sources and frozen versions."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.scenarios import (
    CONTRACT,
    SCENES,
    ScenarioSelection,
    catalogue,
    earliest_change,
    quality_metrics,
    resolve,
)


@pytest.mark.parametrize("scene", SCENES)
def test_preset_has_five_prompt_pairs_and_no_detail_controls(scene):
    config = resolve({"scenario_id": scene, "scenario_version": "2.0.0"})
    assert len(config["stages"]) == 5
    assert set(config["selection"]) == {"scenario_id", "scenario_version"}
    assert "defaults" not in config["resource"]
    for options in config["stages"].values():
        assert set(options["expert_additions"]) == {"pre_guidance", "post_review"}
        assert all(options["expert_additions"].values())
        assert not {"level", "default_level", "level_source", "diagnostic_detail", "service_contract_detail"} & options.keys()
        assert set(options["selected_capabilities"]) == set(config["resource"]["capabilities"])
        assert len(options["declared_fields"]) == sum(len(t["literals"]) for t in config["resource"]["tables"])
    assert config["output_contract"] == CONTRACT
    assert config["hard_requirements"]["evidence_required"] is True
    assert config["hard_requirements"]["upstream_manifest_required"] is True
    assert earliest_change(config, config) is None


@pytest.mark.parametrize("bad", [
    {"manual_overrides": {"S3": {"level": "BASIC"}}},
    {"manual_overrides": {}}, {"level": "DETAILED"},
    {"required_capabilities": []}, {"excluded_capabilities": ["core"]},
    {"scenario_id": "../secrets"}, {"scenario_version": "1.0.0"}, {"confirmed_by": "admin"},
])
def test_removed_controls_and_untrusted_selection_are_rejected(bad):
    with pytest.raises(ValueError):
        resolve(ScenarioSelection.model_validate({"scenario_id": SCENES[0], "scenario_version": "2.0.0", **bad}))


def legacy_configuration():
    # Explicit synthetic old snapshot: kept byte-for-byte as history on upgrade.
    old = resolve({"scenario_id": SCENES[0], "scenario_version": "2.0.0"})
    old["scenario_version"] = "1.0.0"
    old["output_contract"] = "zhigou-scenario-stage/1.0.0"
    old["selection"].update(scenario_version="1.0.0", manual_overrides={"S3": {"level": "BASIC"}},
                            required_capabilities=[], excluded_capabilities=[])
    for options in old["stages"].values():
        options["level"] = "BASIC"
    old["resource_digest"] = "synthetic-old-resource"
    old["digest"] = semantic_hash(old)
    return old


def test_legacy_migration_is_explicit_invalidates_s1_and_preserves_history():
    from zhigou_toolchain.services.modeling_scenarios import install
    session = {"revision": 1, "checks": [], "outputs": [], "events": []}
    user = SimpleNamespace(principal_id="synthetic")
    old = legacy_configuration()
    install(session, old, user)
    session["outputs"] = [{"stage": 1, "status": "CURRENT", "digest": "old"}]
    session["expert"]["stages"]["1"]["configuration"]["pre_guidance_prompt"] = "Retain human text"
    previous = deepcopy(session["scenario"])
    new = resolve({"scenario_id": SCENES[0], "scenario_version": "2.0.0"})
    install(session, new, user)
    assert session["scenario"]["history"][-1] == {k: v for k, v in previous.items() if k != "history"}
    assert session["scenario"]["effective"] == new
    assert session["events"][-1]["from_stage"] == 1
    assert session["outputs"][0]["status"] == "STALE"
    assert all(v["status"] == "DRAFT" and v["confirmed_by"] is None for v in session["expert"]["stages"].values())
    assert session["expert"]["stages"]["1"]["configuration"]["pre_guidance_prompt"] == "Retain human text"


@pytest.mark.parametrize("operation", ["modeling.profile", "modeling.proposal", "modeling.semantic.check",
    "modeling.expert.save", "modeling.expert.reaudit", "compile.build", "review.finalize", "package.export"])
def test_legacy_direct_execution_requires_migration(operation):
    from zhigou_toolchain.services.errors import ServiceBoundaryError
    from zhigou_toolchain.services.modeling_expert import before, initial_state
    from zhigou_toolchain.services.models import OperationRequest
    session = {"scenario": {"effective": legacy_configuration()}, "expert": initial_state()}
    with pytest.raises(ServiceBoundaryError, match="Select and save") as error:
        before(session, OperationRequest(operation))
    assert error.value.code == "SCENARIO_PRESET_MIGRATION_REQUIRED"


def test_tree_preset_keeps_baseline_inspection_obligations():
    config = resolve({"scenario_id": "ancient_tree_inspection", "scenario_version": "2.0.0"})
    assert "inspections" in config["hard_requirements"]["required_capabilities"]
    assert all("inspections" in options["selected_capabilities"] for options in config["stages"].values())


def test_legacy_session_does_not_block_source_ingestion_or_readonly_migration_preview():
    from zhigou_toolchain.services.modeling_expert import before, initial_state
    from zhigou_toolchain.services.models import OperationRequest
    session = {"scenario": {"effective": legacy_configuration()}, "expert": initial_state()}
    for operation in ("source.batch", "ingestion.run", "modeling.scenario.preview", "modeling.scenario.save"):
        before(session, OperationRequest(operation))


@pytest.mark.parametrize("level", ["BASIC", "STANDARD", "DETAILED"])
def test_historical_view_is_readonly_and_preserves_original_shapes(level):
    from zhigou_toolchain.modeling.delivery.legacy_scene_view import (
        contracts as historical_contracts,
    )
    from zhigou_toolchain.modeling.five_stage.scenario_outputs import contracts
    config = resolve({"scenario_id": SCENES[0], "scenario_version": "2.0.0"})
    old = deepcopy(config)
    old.update(scenario_version="1.0.0", output_contract="zhigou-scenario-stage/1.0.0")
    old["stages"]["S5"].update(level=level, included_optional_fields=config["stages"]["S5"]["declared_fields"])
    snapshot = deepcopy(old)
    rows = historical_contracts(old, "synthetic-package")
    assert old == snapshot
    assert ("parameters" in rows[0]) is (level != "BASIC")
    assert ("filters" in rows[0]) is (level == "DETAILED")
    with pytest.raises(ValueError, match="MIGRATION_REQUIRED"):
        contracts(old, "synthetic-package")
    old["resource"]["rules"]["identity"] = "tampered"
    with pytest.raises(ValueError, match="DIGEST_MISMATCH"):
        historical_contracts(old, "synthetic-package")


def test_independent_quality_never_guesses_accuracy():
    assert quality_metrics([], None)["status"] == "NOT_EVALUATED_NO_INDEPENDENT_LABELS"
    assert quality_metrics([], {"objects": [], "relations": [], "attributes": []})["objects"]["precision"] is None
    result = quality_metrics([{"kind": "objects", "key": "a"}, {"kind": "objects", "key": "b"}],
                             {"objects": ["a", "c"], "relations": [], "attributes": []})
    assert result["objects"] == {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}
    assert len(catalogue()) == 3


def test_resolved_scene_context_passes_original_privacy_gate():
    from zhigou_toolchain.modeling.five_stage.expert_runtime import private_check
    from zhigou_toolchain.modeling.five_stage.scenarios import stage_context
    for scene in catalogue():
        resolved = resolve({"scenario_id": scene["scenario_id"], "scenario_version": scene["scenario_version"]})
        for stage in range(1, 6):
            private_check(stage_context(resolved, stage))


def test_runtime_uses_frozen_resource_and_detects_tampering(monkeypatch):
    from copy import deepcopy

    from zhigou_toolchain.modeling.five_stage.scenario_outputs import contracts
    from zhigou_toolchain.modeling.five_stage.scenarios import frozen_scene
    from zhigou_toolchain.services.modeling_scenarios import selected_tables
    original = resolve({"scenario_id": "organization_management", "scenario_version": "2.0.0"})
    monkeypatch.setattr("zhigou_toolchain.modeling.five_stage.scenarios.load_scene", lambda *_: (_ for _ in ()).throw(AssertionError("No hot loading in an active run")))
    assert selected_tables(original, "S3") and contracts(original)
    bad = deepcopy(original)
    bad["resource"]["rules"]["time"] = "invent dates"
    with pytest.raises(ValueError, match="DIGEST_MISMATCH"):
        frozen_scene(bad)


def test_scene_updates_preserve_human_checkpoints_even_with_similar_ids():
    from types import SimpleNamespace

    from zhigou_toolchain.services.modeling_scenarios import install
    session = {"revision": 1, "checks": [], "outputs": [], "events": []}
    original = resolve({"scenario_id": "organization_management", "scenario_version": "2.0.0"})
    user = SimpleNamespace(principal_id="synthetic-scope-expert")
    install(session, original, user)
    custom = {"criterion_id": "scene.custom_must_retain", "description": "Synthetic additional expert evidence requirement", "required": True, "source": "EXPLICIT_SYNTHETIC_HUMAN_REQUIREMENT"}
    session["expert"]["stages"]["4"]["configuration"]["criteria"].append(custom)
    changed = resolve({"scenario_id": "ancient_tree_inspection", "scenario_version": "2.0.0"})
    install(session, changed, user)
    assert custom in session["expert"]["stages"]["4"]["configuration"]["criteria"]


def test_scene_checkpoint_id_collision_requires_explicit_expert_resolution():
    from types import SimpleNamespace

    from zhigou_toolchain.services.errors import ServiceBoundaryError
    from zhigou_toolchain.services.modeling_expert import initial_state
    from zhigou_toolchain.services.modeling_scenarios import install
    session = {"revision": 1, "checks": [], "outputs": [], "events": [], "expert": initial_state()}
    config = resolve({"scenario_id": "organization_management", "scenario_version": "2.0.0"})
    session["expert"]["stages"]["1"]["configuration"]["criteria"].append({"criterion_id": config["stages"]["S1"]["criterion_id"],
        "description": "An older human-owned condition with a colliding identifier", "source": "HUMAN", "required": True})
    with pytest.raises(ServiceBoundaryError) as error:
        install(session, config, SimpleNamespace(principal_id="synthetic"))
    assert error.value.code == "SCENARIO_CRITERION_NAMESPACE_CONFLICT"


def test_scope_coverage_retains_required_optional_and_missing_source_values():
    from zhigou_toolchain.modeling.five_stage.scenario_outputs import scope_coverage
    config = resolve({"scenario_id": "organization_management", "scenario_version": "2.0.0"})
    candidates = [{"body": {"candidate_type": "CLASS_ASSERTION", "subject_iri": "urn:synthetic:employee", "object_iri": "https://example.org/ontology/Employee"}}]
    coverage = scope_coverage(config, candidates)
    employee = next(t for t in coverage["tables"] if t["object_family"] == "employees")
    assert employee["objects"] == 1
    identity = next(f for f in employee["fields"] if f["field"] == "employee_id")
    assert identity["scope_kind"] == "REQUIRED_CAPABILITY" and identity["subjects_without_value_candidate"] == 1
    optional = next(f for f in employee["fields"] if f["field"] == "job_title")
    assert optional["status"] == "NO_OR_PARTIAL_VALUE_CANDIDATES" and optional["subjects_without_value_candidate"] == 1
