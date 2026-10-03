"""Independent labels/metrics: no calls from generation or repair modules."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import Field, model_validator

from .expert import ClosedModel
from .scenarios import quality_metrics


class IndependentLabel(ClosedModel):
    kind: Literal["objects", "relations", "attributes"]
    key: str = Field(min_length=1, max_length=4000)
    capability: str

    @model_validator(mode="after")
    def typed_key(self):
        value = json.loads(self.key)
        length = {"objects": 2, "relations": 3, "attributes": 5}[self.kind]
        if not isinstance(value, list) or len(value) != length or any(not isinstance(v, str) for v in value[:3 if self.kind == "attributes" else length]):
            raise ValueError("SCENARIO_GOLD_MATCH_UNIT_INVALID")
        if self.kind == "attributes" and any(v is not None and not isinstance(v, str) for v in value[3:]):
            raise ValueError("SCENARIO_GOLD_TERM_TYPE_INVALID")
        if self.key != match_key(value):
            raise ValueError("SCENARIO_GOLD_KEY_NOT_CANONICAL")
        return self


class ScenarioGold(ClosedModel):
    scenario_id: str
    label_set_id: str = Field(min_length=1, max_length=150)
    version: str
    matching: Literal["EXACT_TYPED_KEY_SET_V1"]
    projection: Literal["PREDECLARED_CAPABILITY_MEMBERSHIP_V1"]
    labels: list[IndependentLabel] = Field(max_length=10000)
    nature: Literal["INDEPENDENT_SYNTHETIC_LABELS_NOT_LIVE_QUALITY"]

    @model_validator(mode="after")
    def registered_projection(self):
        from .scenarios import SCENES
        if self.scenario_id not in SCENES:
            raise ValueError("SCENARIO_GOLD_SCENE_INVALID")
        if len({(r.kind, r.key) for r in self.labels}) != len(self.labels):
            raise ValueError("SCENARIO_GOLD_DUPLICATE_MATCH_UNIT")
        return self


def match_key(parts):
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def actual_units(graph):
    from rdflib import OWL, RDF
    from rdflib import Literal as RDFLiteral
    rows = []
    for subject, predicate, obj in graph:
        if predicate == RDF.type:
            if obj == OWL.NamedIndividual:
                continue  # Declaration, not the predeclared domain-type matching unit.
            rows.append({"kind": "objects", "key": match_key([str(subject), str(obj)])})
        elif isinstance(obj, RDFLiteral):
            rows.append({"kind": "attributes", "key": match_key([str(subject), str(predicate), str(obj), str(obj.datatype) if obj.datatype else None, obj.language])})
        else:
            rows.append({"kind": "relations", "key": match_key([str(subject), str(predicate), str(obj)])})
    return rows


def evaluate(graph, frozen_gold, configuration):
    if frozen_gold is None:
        return quality_metrics([], None)
    gold = ScenarioGold.model_validate(frozen_gold)
    if gold.scenario_id != configuration["scenario_id"]:
        return {"status": "NOT_EVALUATED_LABEL_SCOPE_MISMATCH"}
    validate_projection(gold, configuration)
    caps = configuration["stages"]["S3"]["selected_capabilities"]
    projected = {kind: [label.key for label in gold.labels if label.kind == kind and label.capability in caps]
                 for kind in ("objects", "relations", "attributes")}
    return {**quality_metrics(actual_units(graph), projected), "label_set_id": gold.label_set_id, "label_version": gold.version,
        "projection": gold.projection, "selected_capabilities": caps, "nature": gold.nature,
        "comparison_warning": "Different scenes have different label scopes; only independent labels support these metrics"}


def validate_projection(gold, configuration):
    from .scenarios import frozen_scene
    if any(label.capability not in frozen_scene(configuration)["capabilities"] for label in gold.labels):
        raise ValueError("SCENARIO_GOLD_PROJECTION_INVALID")
