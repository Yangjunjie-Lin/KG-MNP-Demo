"""Read-only report boundary; imported scores never grant authority."""
import math

from jsonschema import Draft202012Validator

from zhigou_toolchain.contracts.canonical import canonical_json_bytes, semantic_hash

from .contracts import REPORT_SCHEMA


def inspect_report(report, *, max_bytes=800000):
    def reject_private(value, depth=0):
        if depth > 64:
            raise ValueError("RESEARCH_REPORT_NESTING_LIMIT")
        if isinstance(value, dict):
            forbidden = {"gold", "gold_triples", "gold_ontology", "target_ontology", "private_gold", "api_key", "authorization", "access_token"}
            if any(str(k).lower().replace("-", "_") in forbidden for k in value):
                raise ValueError("PRIVATE_SCORING_OR_CREDENTIAL_CONTENT_FORBIDDEN")
            for child in value.values():
                reject_private(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                reject_private(child, depth + 1)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("NON_FINITE_RESEARCH_VALUE")
    reject_private(report)
    if len(canonical_json_bytes(report)) > max_bytes:
        raise ValueError("RESEARCH_REPORT_TOO_LARGE")
    Draft202012Validator(REPORT_SCHEMA).validate(report)
    if report["failure_count"] > report["sample_count"]:
        raise ValueError("INVALID_FAILURE_DENOMINATOR")
    return {"report": report, "sha256": semantic_hash(report), "validation": "REPORT_SCHEMA_ONLY",
        "source_authenticity": "UNVERIFIED_EXTERNAL_REPORT", "authority": "READ_ONLY_RESEARCH_DISPLAY", "production_allowed": False}
