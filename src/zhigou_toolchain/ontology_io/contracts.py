"""Gold-free generation input and predeclared, bounded experiment protocol."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EvaluationScope = Literal["LOCAL_HOLDOUT", "OFFICIAL_TEST", "ENGINEERING_CHECK", "ADAPTED_ANALYSIS"]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelingInput(Closed):
    sample_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    benchmark_id: str
    task_id: str
    dataset_version: str
    split: str
    evaluation_scope: EvaluationScope
    group_id: str
    mode: Literal["TEXT_NEW", "TEXT_EXTEND", "CQS_TBOX", "SCHEMA_ABOX", "RECORDS_TEXT"]
    text: str = Field(default="", max_length=200000)
    records: list[dict[str, str]] = Field(default_factory=list, max_length=10000)
    competency_questions: list[str] = Field(default_factory=list, max_length=1000)
    initial_triples: list[tuple[str, str, str]] = Field(default_factory=list, max_length=10000)
    allowed_schema: dict = Field(default_factory=dict)
    requirements: list[str] = Field(default_factory=list)
    identity_policy: Literal["PER_SAMPLE_CANDIDATE_LABEL_V1"] = "PER_SAMPLE_CANDIDATE_LABEL_V1"
    temporal_policy: str = "ONLY_EXPLICIT_TIME_NO_IMPLICIT_HISTORY_MERGE"
    resources: list[dict[str, str]] = Field(default_factory=list)


class Budget(Closed):
    max_calls: int = Field(default=4, ge=1, le=20)
    max_input_characters: int = Field(default=24000, ge=100, le=200000)
    max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    max_total_tokens: int = Field(default=24000, ge=256, le=200000)
    context_window_tokens: int = Field(default=32768, ge=512, le=200000)
    token_accounting_policy: Literal["UTF8_UPPER_BOUND_V1"] = "UTF8_UPPER_BOUND_V1"


class Protocol(Closed):
    protocol_id: str
    model_id: str
    declared_revision: str
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"] | None = None
    systems: list[Literal["DirectGeneralLLM", "TwoAgentV3", "DirectBudgetControl", "NoRetrieval", "NoConstrainedExtraction", "NoValidationFeedback"]]
    budget: Budget = Field(default_factory=Budget)
    replicates: int = Field(default=3, ge=1, le=10)
    matching: Literal["exact", "fuzzy", "semantic"] = "exact"
    primary_metrics: list[str] = Field(default_factory=lambda: ["graph_similarity"])
    bootstrap_samples: int = Field(default=2000, ge=100, le=10000)
    statistics_seed: int = 1729
    primary_test_correction: Literal["HOLM"] = "HOLM"
    truncation_policy: Literal["REJECT_FOR_ALL_SYSTEMS"] = "REJECT_FOR_ALL_SYSTEMS"
    invalid_prediction_policy: Literal["UNSCORABLE_NO_SUCCESS_SUBSET_AGGREGATION"] = "UNSCORABLE_NO_SUCCESS_SUBSET_AGGREGATION"
    approval: Literal["NOT_GRANTED"] = "NOT_GRANTED"
    release_status: Literal["NOT_RELEASED"] = "NOT_RELEASED"

    @model_validator(mode="after")
    def unique_variants_and_metrics(self):
        if not self.systems or len(set(self.systems)) != len(self.systems):
            raise ValueError("SYSTEMS_MUST_BE_NONEMPTY_AND_UNIQUE")
        if not self.primary_metrics or len(set(self.primary_metrics)) != len(self.primary_metrics):
            raise ValueError("PRIMARY_METRICS_MUST_BE_NONEMPTY_AND_UNIQUE")
        return self


STRING = {"type": "string", "minLength": 1, "maxLength": 1000}
SHA256 = {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"}
COUNT = {"type": "integer", "minimum": 0}
METRIC_SCHEMA = {
    "type": "object", "required": ["name", "source", "matching", "value", "unit", "numerator", "denominator", "status"],
    "properties": {**{key: STRING for key in ("name", "source", "matching", "unit")},
        "value": {"type": ["number", "null"]}, "status": {"enum": ["MEASURED", "NOT_RUN", "UNSCORABLE"]},
        "numerator": {"type": ["number", "null"]}, "denominator": {"type": ["number", "null"], "minimum": 0},
        "sample_count": COUNT, "failure_count": COUNT},
    "allOf": [{"if": {"properties": {"status": {"enum": ["NOT_RUN", "UNSCORABLE"]}}}, "then": {"properties": {"value": {"type": "null"}}}},
        {"if": {"properties": {"status": {"const": "MEASURED"}}}, "then": {"properties": {"value": {"type": "number"}}}}],
    "additionalProperties": False,
}

REPORT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:zhigou:ontology-io-report:1.0.0", "type": "object",
    "required": ["schema_version", "benchmark_id", "task_id", "dataset_version", "split", "evaluation_scope", "input_manifest_sha256",
        "prediction_manifest_sha256", "scorer_commit", "scorer_config_sha256", "system_id", "model_id", "declared_revision", "observed_model_ids",
        "run_id", "source_commit", "source_fingerprint_sha256", "metrics", "sample_count", "failure_count", "status", "comparison", "resources", "limitations"],
    "properties": {
        **{key: STRING for key in ("benchmark_id", "task_id", "dataset_version", "split", "system_id", "model_id", "declared_revision", "run_id")},
        **{key: SHA256 for key in ("input_manifest_sha256", "prediction_manifest_sha256", "scorer_config_sha256", "source_fingerprint_sha256", "protocol_sha256")},
        "schema_version": {"const": "1.0.0"}, "status": {"enum": ["MEASURED", "NOT_RUN", "UNSCORABLE", "AWAITING_OFFICIAL_SCORE"]},
        "evaluation_scope": {"enum": ["LOCAL_HOLDOUT", "OFFICIAL_TEST", "ENGINEERING_CHECK", "ADAPTED_ANALYSIS", "HUMAN_EVALUATION"]},
        "source_commit": {"type": ["string", "null"], "pattern": "^[0-9a-f]{40,64}$"},
        "scorer_commit": {"type": ["string", "null"], "pattern": "^[0-9a-f]{40,64}$"},
        "sample_count": COUNT, "failure_count": COUNT, "observed_model_ids": {"type": "array", "items": STRING, "uniqueItems": True},
        "comparison": {"type": ["object", "null"]}, "resources": {"type": "array", "items": {"type": "object"}},
        "limitations": {"type": "array", "items": STRING}, "samples": {"type": "array", "items": {"type": "object"}},
        "metrics": {"type": "array", "items": METRIC_SCHEMA, "maxItems": 100},
    },
    "allOf": [
        {"if": {"properties": {"status": {"enum": ["NOT_RUN", "AWAITING_OFFICIAL_SCORE"]}}},
         "then": {"properties": {"metrics": {"items": {"properties": {"status": {"const": "NOT_RUN"}, "value": {"type": "null"}}}}}}},
        {"if": {"properties": {"status": {"const": "MEASURED"}}}, "then": {"properties": {
            "sample_count": {"minimum": 1}, "failure_count": {"const": 0},
            **{key: {"type": "string"} for key in ("source_commit", "scorer_commit", "input_manifest_sha256", "prediction_manifest_sha256", "scorer_config_sha256", "source_fingerprint_sha256")},
        }}},
    ],
    "additionalProperties": True,
}
