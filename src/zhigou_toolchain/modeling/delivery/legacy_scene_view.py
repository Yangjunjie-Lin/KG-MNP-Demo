"""Read-only reconstruction of already exported v1 scene contract views.

Never imported by generation, selection or the Worker. This preserves archive
verification without permitting old detail settings in new executions.
"""
from zhigou_toolchain.contracts.canonical import semantic_hash

from .exchange_io import require


def contracts(configuration, package_id):
    require(configuration.get("output_contract") == "zhigou-scenario-stage/1.0.0"
            and configuration.get("scenario_version") == "1.0.0", "HISTORICAL_SCENE_VERSION_UNSUPPORTED")
    scene = configuration.get("resource", {})
    require(scene.get("resource_digest") == configuration["resource_digest"]
            and semantic_hash({k: v for k, v in scene.items() if k != "resource_digest"}) == configuration["resource_digest"],
            "SCENARIO_FROZEN_RESOURCE_DIGEST_MISMATCH")
    options = configuration["stages"]["S5"]
    require(options["level"] in {"BASIC", "STANDARD", "DETAILED"}, "HISTORICAL_SCENE_LEVEL_INVALID")
    result = []
    for table in scene["tables"]:
        if table["record_id"] not in options["enabled_object_families"]:
            continue
        row = {"operation": "ods.query", "object_family": table["record_id"], "class_iri": table["class_iri"],
            "package_id": package_id, "status": "REGISTERED_READ_INTERFACE_REQUIRES_PACKAGE_IMPORT",
            "permissions": ["package:read"], "deployment": "NOT_ASSERTED", "mutates_business": False}
        if options["level"] != "BASIC":
            row.update(parameters={"package_id": "required native package identifier", "class_iri": table["class_iri"], "limit": "1..1000", "offset": "0..1000000"},
                selected_fields=[f for f in options["included_optional_fields"] if f.split(".")[0] == table["record_id"]],
                errors=["FORBIDDEN", "PACKAGE_NOT_FOUND", "REQUEST_INVALID"],
                example={"class_iri": table["class_iri"], "limit": 10, "offset": 0, "execution": "NOT_EXECUTED_BY_CONTRACT"})
        if options["level"] == "DETAILED":
            row.update(filters={"one_of": ["class_iri", "instance_iri"], "combination": "EXCLUSIVE_EXACT_MATCH"},
                preconditions=["verified package imported in original Registry", "current package:read permission"],
                idempotency="READ_ONLY_SAME_FROZEN_PACKAGE", composition="Read returned source-bound relationships; no arbitrary combined-query feature asserted",
                action_preview={"status": "UNSUPPORTED_NO_REGISTERED_SCENE_ACTION", "executed": False})
        result.append(row)
    return result
