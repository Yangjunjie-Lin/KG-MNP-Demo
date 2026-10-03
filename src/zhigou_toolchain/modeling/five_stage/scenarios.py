"""Three versioned scene Prompt presets and fixed source adapters.

This is a projection/configuration layer over the original session and providers,
not another coordinator, authority store, quality score or executable template.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Literal

from pydantic import Field

from zhigou_toolchain.contracts.canonical import semantic_hash

from .expert import ClosedModel
from .registry import resource_root

SCENES = ("organization_management", "ancient_tree_inspection", "equipment_maintenance")
VERSION = "2.0.0"
CONTRACT = "zhigou-scenario-stage/2.0.0"
HARD_REQUIREMENTS = {"evidence_required": True, "original_values_required": True,
    "scope_approval_required": True, "human_review_required": True, "upstream_manifest_required": True,
    "checks": ["integrity", "explicit_target_coverage", "shacl", "owl_profile", "hermit"],
    "actions": "NO_NEW_AUTHORITY", "quality": "NO_ACCURACY_WITHOUT_INDEPENDENT_LABELS"}

SCENARIO_GENERATE_PROMPT = "在通用任务和已确认专家指导下，使用本次冻结场景的当前阶段 Prompt 预设完成方法。只生成已批准范围内、有来源支撑的内容，满足原输出 Schema 和固定领域词汇约束。资料缺失应明确报告，不编造属性、事件、时间、单位、编码或新 IRI。场景模板不改变硬规则、证据义务、预算或批准权限。"
SCENARIO_REVIEW_PROMPT = "按冻结的场景审核 Prompt、专家检查点和原输出契约审核当前候选与实际检查报告，定位具体问题、证据和修订路线。检查身份、关系、字段、时间、来源及范围的一致性；缺失资料不代表事实不存在，不放过硬检查失败，不把模型自评当成独立质量分数。需要改范围或场景的问题交专家处理。"
SCENARIO_REVISE_PROMPT = "保持本轮场景 Prompt 版本、输出契约和专家标准不变，仅提交有依据的受限补丁。不能缩小必需范围、删掉失败项、放宽规则或改验收答案来获得通过。需要改变冻结条件时交专家形成新版本；修订后由原程序重新检查、审核。"


class ScenarioSelection(ClosedModel):
    scenario_id: Literal["organization_management", "ancient_tree_inspection", "equipment_maintenance"]
    scenario_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


class FieldRule(ClosedModel):
    predicate_iri: str
    datatype: Literal["string"]
    capability: str


class ReferenceRule(ClosedModel):
    field: str
    target_space: str
    predicate_iri: str


class TableRule(ClosedModel):
    record_id: str
    source_name: str
    class_iri: str
    id_field: str
    literals: dict[str, FieldRule]
    references: list[ReferenceRule]
    capability: str


class Capability(ClosedModel):
    description: str
    required: bool = False


class PackReference(ClosedModel):
    pack_id: str
    pack_version: str


class SceneResource(ClosedModel):
    scenario_id: str
    scenario_version: str
    name: str
    purpose: str
    nature: Literal["SYNTHETIC_ENGINEERING_TEMPLATE_NOT_EXPERT_APPROVAL"]
    domain_pack: PackReference
    capabilities: dict[str, Capability]
    tables: list[TableRule]
    namespace: str
    query_asset_id: str
    additions: list[list[str]] = Field(min_length=5, max_length=5)
    output_contract: Literal["zhigou-scenario-stage/2.0.0"]
    rules: dict[str, str]
    fixture_ref: str


def load_scene(identifier, version=VERSION):
    if identifier not in SCENES or version != VERSION:
        raise ValueError("SCENARIO_VERSION_UNAVAILABLE")
    raw = json.loads(resource_root().joinpath("scenarios", identifier + ".json").read_bytes())
    resource = SceneResource.model_validate(raw).model_dump()
    if resource["scenario_id"] != identifier or resource["scenario_version"] != version:
        raise ValueError("SCENARIO_RESOURCE_IDENTITY_MISMATCH")
    ids = {t["record_id"] for t in resource["tables"]}
    if len(ids) != len(resource["tables"]) or "core" not in resource["capabilities"]:
        raise ValueError("SCENARIO_RESOURCE_INVALID")
    if any(len(pair) != 2 or any(not text.strip() for text in pair) for pair in resource["additions"]):
        raise ValueError("SCENARIO_PROMPT_PAIR_INVALID")
    for table in resource["tables"]:
        if table["capability"] not in resource["capabilities"] or table["id_field"] not in table["literals"]:
            raise ValueError("SCENARIO_INPUT_CONTRACT_INVALID")
        if any(r["target_space"] not in ids for r in table["references"]):
            raise ValueError("SCENARIO_REFERENCE_CONTRACT_INVALID")
        if any(r["capability"] not in resource["capabilities"] for r in table["literals"].values()):
            raise ValueError("SCENARIO_FIELD_CONTRACT_INVALID")
    return {**resource, "resource_digest": semantic_hash(resource)}


def catalogue():
    return [load_scene(identifier) for identifier in SCENES]


def resolve(selection: ScenarioSelection | dict):
    selection = ScenarioSelection.model_validate(selection)
    scene = load_scene(selection.scenario_id, selection.scenario_version)
    caps = scene["capabilities"]
    required = {"core", *(name for name, policy in caps.items() if policy["required"])}
    # Fixed registered input contract, not a hidden per-stage detail preset.
    # Every declared source field remains visible to the original validation.
    selected = sorted(caps)
    tables = scene["tables"]
    stages = {}
    for index in range(1, 6):
        key = f"S{index}"
        stages[key] = {"selected_capabilities": list(selected),
            "enabled_object_families": [t["record_id"] for t in tables],
            "declared_fields": sorted(t["record_id"] + "." + f for t in tables for f in t["literals"]),
            "expert_additions": {"pre_guidance": scene["additions"][index - 1][0], "post_review": scene["additions"][index - 1][1]},
            "criterion_id": "scene." + scene["scenario_id"] + "." + key}
    result = {"selection": selection.model_dump(), "scenario_id": scene["scenario_id"], "scenario_version": scene["scenario_version"],
        "resource": deepcopy(scene),
        "resource_digest": scene["resource_digest"], "domain_pack": scene["domain_pack"], "namespace": scene["namespace"],
        "stages": stages, "output_contract": CONTRACT,
        "hard_requirements": {**deepcopy(HARD_REQUIREMENTS), "required_capabilities": sorted(required)}, "rules": scene["rules"]}
    result["stage_digests"] = {k: semantic_hash({"resource": scene["resource_digest"], "options": v}) for k, v in stages.items()}
    result["digest"] = semantic_hash(result)
    return result


def frozen_scene(configuration):
    """Run from the captured resource, never hot-load a later file at the same ID."""
    require_current(configuration)
    scene = deepcopy(configuration.get("resource"))
    if not isinstance(scene, dict) or scene.get("resource_digest") != configuration["resource_digest"]:
        raise ValueError("SCENARIO_FROZEN_RESOURCE_MISSING")
    resource = {k: v for k, v in scene.items() if k != "resource_digest"}
    SceneResource.model_validate(resource)
    if semantic_hash(resource) != configuration["resource_digest"]:
        raise ValueError("SCENARIO_FROZEN_RESOURCE_DIGEST_MISMATCH")
    return scene


def earliest_change(old, new):
    if old is None or old["resource_digest"] != new["resource_digest"]:
        return 1
    return next((s for s in range(1, 6) if old["stage_digests"][f"S{s}"] != new["stage_digests"][f"S{s}"]), None)


def require_current(configuration):
    """Old frozen records stay readable, but cannot silently run new semantics."""
    if configuration and (configuration.get("output_contract") != CONTRACT or configuration.get("scenario_version") != VERSION):
        raise ValueError("SCENARIO_PRESET_MIGRATION_REQUIRED")


def stage_context(effective, stage):
    require_current(effective)
    key = f"S{stage}"
    return {"scenario_id": effective["scenario_id"], "scenario_version": effective["scenario_version"],
        "resource_digest": effective["resource_digest"], "effective_configuration_digest": effective["digest"],
        "stage_configuration_digest": effective["stage_digests"][key],
        "effective_stage_config": effective["stages"][key], "selected_scope": effective["stages"]["S1"],
        "allowed_extensions": effective["stages"][key]["selected_capabilities"],
        "output_contract": CONTRACT, "hard_requirements": effective["hard_requirements"], "rules": effective["rules"]}


def quality_metrics(actual, independent_labels):
    """Pure independent evaluator; never used in a generation/review context."""
    if independent_labels is None:
        return {"status": "NOT_EVALUATED_NO_INDEPENDENT_LABELS"}
    output = {"status": "EVALUATED_INDEPENDENT_LABELS", "matching": "EXACT_TYPED_KEY_SET_V1"}
    for kind in ("objects", "relations", "attributes"):
        predicted = {r["key"] for r in actual if r["kind"] == kind}
        expected = set(independent_labels[kind])
        tp, fp, fn = len(predicted & expected), len(predicted - expected), len(expected - predicted)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        output[kind] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}
    return output
