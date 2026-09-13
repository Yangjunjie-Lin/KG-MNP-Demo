"""Loss-accounted native package inspection; never invent missing v3 authority.

A .kgop digest of an oracle is not the oracle's independent expected rows.
Likewise evidence IDs do not reconstruct licensed source snapshots/locators.
This preflight explicitly records which additional bound inputs are needed.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

from rdflib import OWL, RDF, Graph

from zhigou_toolchain.semantic_kernel.packaging.archive import (
    archive_mapping_bytes,
    verify_kgop,
)
from zhigou_toolchain.semantic_kernel.rdf.canonical import graph_semantic_digest

from .v3 import require

GRAPH_PATHS = {"ontology": "ontology/effective-tbox.ttl", "instances": "data/abox.ttl", "shapes": "shapes/effective-shapes.ttl"}


def capture_native(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64_000_000, "NATIVE_ARCHIVE_SIZE_OR_LINK")
    with path.open("rb") as stream:
        raw = stream.read(64_000_001)
    require(len(raw) <= 64_000_000, "NATIVE_ARCHIVE_SIZE_OR_LINK")
    # Verify exactly the captured bytes. Never verify one file then export a
    # later, possibly replaced reread of it.
    with tempfile.TemporaryDirectory(prefix="zhigou-native-v3-preflight-") as temporary:
        snapshot = Path(temporary) / "snapshot.kgop"
        snapshot.write_bytes(raw)
        verification = verify_kgop(snapshot, max_uncompressed_bytes=64_000_000)
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        files = {name: archive.read(name) for name in verification["contents"]}
    return raw, files, verification


def inspect_native(path):
    raw, files, verification = capture_native(path)
    report = analyze_native(files, verification)
    require(hashlib.sha256(raw).hexdigest() == report["native_archive_sha256"], "NATIVE_SNAPSHOT_CHANGED")
    return report


def analyze_native(files, verification):
    manifest = json.loads(files["ontology-package.json"])
    confirmed = json.loads(files["source/confirmed-modeling-package.json"])
    provenance = json.loads(files["provenance/statement-provenance-manifest.json"])
    plan = json.loads(files["validation/competency-question-test-plan.json"])
    graphs = {role: Graph().parse(data=files[name].decode("utf-8"), format="turtle") for role, name in GRAPH_PATHS.items()}
    sources = sorted({ref for row in provenance["statements"] for ref in row["source_asset_refs"]})
    evidence = sorted({ref for row in provenance["statements"] for ref in row["evidence_record_refs"]})
    missing = [
        {"code": "BOUND_V3_SCOPE_CATALOG_RULES_REQUIRED", "required": ["scope and identity/time policy", "catalog identifiers/labels", "approved rule sources"],
         "reason": "Do not derive approved business rules or identity policy from observed sample values."},
        {"code": "BOUND_SOURCE_SNAPSHOTS_AND_LOCATORS_REQUIRED", "source_ids": sources, "evidence_ids": evidence,
         "reason": "Native provenance references are retained; complete exportable snapshots and v3 locators require the original bound modeling inputs and permission/licence policy."},
        {"code": "BOUND_MAPPING_EXECUTION_REQUIRED", "native_mapping_ref": "mappings/mapping-plan.json",
         "reason": "Native DECLARATIVE_NOT_EXECUTED mapping metadata must not be relabelled as v3 executed entity/fact transforms."},
        {"code": "BOUND_INDEPENDENT_ACCEPTANCE_ROWS_REQUIRED", "native_test_ids": [t["test_id"] for t in plan["tests"]],
         "reason": "Preserve the frozen native oracle hashes. Do not query output to invent the explicit expected multiset required by v3."},
        {"code": "REVIEW_CROSSWALK_REQUIRED", "scope_approval_id": confirmed["scope_approval_id"],
         "review_decision_log_id": confirmed["review_decision_log_id"], "review_semantic_hash": confirmed["review_semantic_hash"],
         "reason": "Existing native review identity remains authoritative; a converter cannot manufacture v3 authenticated actor/time/approval."},
    ]
    declarations = len(list(graphs["instances"].triples((None, RDF.type, OWL.NamedIndividual))))
    return {"schema_version": "1.0.0", "profile": "NATIVE_TO_V3_COMPATIBILITY_PREFLIGHT", "status": "BLOCKED_REQUIRED_BOUND_INPUTS",
        "v3_export_created": False, "native_verified": verification["status"], "native_package_id": manifest["package_id"],
        "native_archive_sha256": verification["archive_sha256"], "native_lock_id": verification["lock_id"],
        "graphs": {role: {"native_path": GRAPH_PATHS[role], "triples": len(graph), "semantic_sha256": graph_semantic_digest(graph)} for role, graph in graphs.items()},
        "auxiliary_named_individual_declarations": declarations,
        "business_fact_count": len(graphs["instances"]) - declarations,
        "missing_bound_inputs": missing, "approval": "NOT_GRANTED_BY_CONVERTER", "release_status": "NOT_RELEASED",
        "limitations": ["Preflight is not an implemented full native-to-v3 exporter", "No native identifiers, signatures, hashes or Registry state are modified",
            "A diagnostic graph snapshot is not an ontology-delivery/3.0.0 package"]}


def diagnostic_bytes(path):
    _raw, files, verification = capture_native(path)
    report = analyze_native(files, verification)
    # Only three graph files and the loss report; no entire repository,
    # research gold, source snapshots or upstream benchmark data are exported.
    selected = {"model/" + role + ".ttl": files[name] for role, name in GRAPH_PATHS.items()}
    selected["diagnostic.json"] = json.dumps({**report, "format": "zhigou-native-ontology-diagnostic/1.0.0"}, ensure_ascii=False, indent=2).encode("utf-8")
    return archive_mapping_bytes(selected)
