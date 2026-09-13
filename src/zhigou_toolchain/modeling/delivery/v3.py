"""Read-only v3 contract inspection and deterministic packaging.

The supplied 3.0.0 schema is pinned, not trusted from an incoming ZIP. Package
review booleans never grant service permissions. Graph loading is isolated and
per-package; shape/report graphs never enter the default business query graph.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from importlib import resources
from io import BytesIO
from pathlib import PurePosixPath

from jsonschema import Draft202012Validator, FormatChecker
from rdflib import OWL, RDF, SH, Dataset, Graph, Literal, URIRef
from rdflib.compare import isomorphic

from zhigou_toolchain.semantic_kernel.security import assert_read_only_query
from zhigou_toolchain.semantic_kernel.validators.competency_questions import _execute

from .validation import shacl_check

SCHEMA_SHA256 = "21519fcac6c85fe1e2b3d2c3bd080e0576a135c2882d9d01326b8dc0cbf8fd80"
SCHEMA_PATH = "contracts/delivery.schema.json"
REQUIRED_DEFINITIONS = {
    "acceptance/baseline.json": "baseline", "acceptance/cases.json": "cases",
    "acceptance/results.json": "results", "acceptance/standardization_cases.json": "standard_cases",
    "data/facts.jsonl": "fact", "data/objects.jsonl": "object",
    "integration/capabilities.json": "capabilities", "integration/context.json": "context",
    "integration/load_contract.json": "load", "mapping/mapping.json": "mapping",
    "model/axioms.json": "axiom_catalog", "model/catalog.json": "catalog", "model/metadata.json": "ontology_metadata",
    "model/rules.json": "rules", "model/scope.json": "scope", "model/terms.json": "term_catalog",
    "provenance/assertions.jsonl": "assertion", "provenance/evidence.jsonl": "evidence", "provenance/sources.json": "sources",
    "quality/issues.jsonl": "issue", "quality/metrics.json": "metrics", "quality/review.json": "review",
    "quality/standardization.json": "standard_report", "quality/validation.json": "validation",
    "standardization/crosswalk.json": "standard_crosswalk", "standardization/profile.json": "standard_profile",
    "standardization/references.json": "standard_references", "version/change_set.json": "change",
    "version/dependencies.lock.json": "dependencies",
}


class DeliveryError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise DeliveryError(code)


def path_name(name):
    path = PurePosixPath(name)
    require(bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name
        and ":" not in name and "\0" not in name and str(path) == name, "UNSAFE_DELIVERY_PATH")
    return name


def read_zip(raw):
    require(0 < len(raw) <= 64_000_000, "ZIP_SIZE_LIMIT")
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        require(len(infos) <= 4096 and sum(i.file_size for i in infos) <= 64_000_000, "ZIP_EXPANSION_LIMIT")
        manifests = [i.filename for i in infos if i.filename == "manifest.json" or i.filename.endswith("/manifest.json")]
        require(len(manifests) == 1, "SINGLE_MANIFEST_REQUIRED")
        prefix = manifests[0].removesuffix("manifest.json")
        files, seen = {}, set()
        for info in infos:
            path_name(info.filename)
            require(info.filename.startswith(prefix), "MIXED_ZIP_ROOTS")
            name = path_name(info.filename[len(prefix):])
            require(name.casefold() not in seen, "DUPLICATE_DELIVERY_PATH")
            require((info.external_attr >> 16) & 0o170000 != 0o120000, "ZIP_SYMLINK_REJECTED")
            require(info.file_size <= 32_000_000 and info.file_size <= max(1, info.compress_size) * 200, "ZIP_ENTRY_LIMIT")
            seen.add(name.casefold())
            files[name] = archive.read(info)
    return files


def term(value):
    if value["type"] == "iri":
        return URIRef(value["value"])
    require(not (value["datatype"] and value["language"]), "LITERAL_DATATYPE_LANGUAGE_CONFLICT")
    return Literal(value["value"], datatype=value["datatype"], lang=value["language"])


def _unique(rows, key):
    values = {row[key]: row for row in rows}
    require(len(values) == len(rows), "DUPLICATE_" + key.upper())
    return values


class V3Delivery:
    def __init__(self, files):
        self.files = dict(files)
        self.schema_bytes = resources.files("zhigou_toolchain.modeling.delivery").joinpath("delivery-v3.schema.json").read_bytes()
        require(hashlib.sha256(self.schema_bytes).hexdigest() == SCHEMA_SHA256, "PINNED_SCHEMA_CHANGED")
        self.schema = json.loads(self.schema_bytes)
        self.graphs = {}

    def read(self, name):
        require(path_name(name) in self.files, "MISSING_DELIVERY_FILE:" + name)
        return self.files[name]

    def document(self, name):
        return json.loads(self.read(name))

    def lines(self, name):
        return [json.loads(line) for line in self.read(name).decode("utf-8").splitlines() if line.strip()]

    def validate(self, value, definition):
        require(definition.startswith("#/$defs/") and definition.split("/")[-1] in self.schema["$defs"], "UNTRUSTED_SCHEMA_REFERENCE")
        Draft202012Validator({**self.schema, "$ref": definition}, format_checker=FormatChecker()).validate(value)

    def inspect(self, *, run_shacl=False, query_timeout_seconds=15, max_query_results=10000):
        from .closure import check_assertions, resolve_pointer

        require(0 < query_timeout_seconds <= 60 and 0 < max_query_results <= 100000, "INVALID_QUERY_LIMITS")
        manifest = self.document("manifest.json")
        self.validate(manifest, "#/$defs/manifest")
        require(self.read(SCHEMA_PATH) == self.schema_bytes, "INCOMING_SCHEMA_NOT_PINNED_V3")
        listed = _unique(manifest["files"], "path")
        require(set(self.files) == {"manifest.json", *listed}, "UNLISTED_OR_MISSING_PAYLOAD")
        for name, definition in REQUIRED_DEFINITIONS.items():
            require(name in listed and listed[name]["schema_ref"] == SCHEMA_PATH + "#/$defs/" + definition, "REQUIRED_SCHEMA_BINDING_MISSING:" + name)
        for name, item in listed.items():
            raw = self.read(name)
            require(len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"], "FILE_DIGEST_MISMATCH:" + name)
            if item["schema_ref"] is not None:
                require(item["schema_ref"].startswith(SCHEMA_PATH + "#/$defs/"), "UNTRUSTED_SCHEMA_REFERENCE")
                values = self.lines(name) if name.endswith(".jsonl") else [self.document(name)]
                for value in values:
                    self.validate(value, "#" + item["schema_ref"].split("#", 1)[1])
        load = self.document(manifest["entrypoint"])
        require(load["protocol"] == manifest["protocol"] and load["schema_version"] == manifest["schema_version"], "LOAD_PROTOCOL_MISMATCH")
        require(manifest["entrypoint"] == "integration/load_contract.json", "UNSUPPORTED_ENTRYPOINT")
        require(load["load_mode"] == "ISOLATED_STAGING" and load["write_policy"] == "NO_AUTOMATIC_PUBLISH", "UNSAFE_LOAD_POLICY")
        require(load["historical_merge"] == "FORBIDDEN_UNLESS_TEMPORAL_POLICY_DEFINED", "HISTORICAL_UNION_FORBIDDEN")
        query_policy = load["query_dataset"]
        require(query_policy["include_roles"] == ["ontology", "instances"] and "shapes" in query_policy["exclude_roles"]
            and query_policy["inference"] == "NONE_EXPLICIT_FACTS", "UNSUPPORTED_QUERY_DATASET")
        declarations = _unique(load["graphs"], "role")
        require(set(declarations) == {"ontology", "instances", "shapes"}, "GRAPH_ROLE_MISMATCH")
        require(len({r["graph_iri"] for r in declarations.values()}) == 3, "GRAPH_IDENTITY_COLLISION")
        require(all(r["path"] == "model/" + role + ".ttl" for role, r in declarations.items()), "GRAPH_PATH_ROLE_MISMATCH")
        self.graphs = {role: Graph().parse(data=self.read(row["path"]).decode("utf-8"), format="turtle") for role, row in declarations.items()}
        dependencies = self.document("version/dependencies.lock.json")
        require(dependencies["external_fetch_allowed"] is False, "EXTERNAL_FETCH_FORBIDDEN")
        imports = _unique(dependencies["imports"], "iri")
        for iri, item in imports.items():
            require(item["path"] in listed and hashlib.sha256(self.read(item["path"])).hexdigest() == item["sha256"], "IMPORT_NOT_PINNED")
            graph = Graph().parse(data=self.read(item["path"]).decode("utf-8"), format="turtle")
            require((URIRef(iri), RDF.type, OWL.Ontology) in graph, "IMPORT_IDENTITY_MISMATCH")
            require(all(str(o) in imports for o in graph.objects(None, OWL.imports)), "IMPORT_NOT_PINNED")
            self.graphs["ontology"] += graph
        require(all(str(o) in imports for graph in self.graphs.values() for o in graph.objects(None, OWL.imports)), "IMPORT_NOT_PINNED")
        facts = _unique(self.lines("data/facts.jsonl"), "fact_id")
        objects = _unique(self.lines("data/objects.jsonl"), "object_id")
        sources = _unique(self.document("provenance/sources.json")["items"], "source_id")
        evidence = _unique(self.lines("provenance/evidence.jsonl"), "evidence_id")
        assertions = _unique(self.lines("provenance/assertions.jsonl"), "assertion_id")
        reconstructed = Graph()
        for fact in facts.values():
            require(fact["graph_iri"] == declarations["instances"]["graph_iri"], "FACT_GRAPH_MISMATCH")
            require(fact["context"]["identity_scope"] == manifest["identity_scope"] and fact["context"]["snapshot_id"] == manifest["snapshot_id"], "FACT_CONTEXT_MISMATCH")
            reconstructed.add((URIRef(fact["subject"]), URIRef(fact["predicate"]), term(fact["object"])))
            require(set(fact["evidence_refs"]) <= evidence.keys() and set(fact["assertion_refs"]) <= assertions.keys(), "FACT_REFERENCE_MISSING")
            for ref in fact["assertion_refs"]:
                assertion = assertions[ref]
                require(assertion["fact_id"] == fact["fact_id"] and assertion["evidence_ref"] in fact["evidence_refs"], "ASSERTION_FACT_MISMATCH")
                require(assertion["source_id"] == evidence[assertion["evidence_ref"]]["source_id"], "ASSERTION_SOURCE_MISMATCH")
        require(len(reconstructed) == len(facts) and isomorphic(reconstructed, self.graphs["instances"]), "FACT_GRAPH_NOT_ISOMORPHIC")
        for obj in objects.values():
            require((URIRef(obj["object_id"]), RDF.type, URIRef(obj["type_iri"])) in reconstructed, "OBJECT_TYPE_MISSING")
            require(obj["identity_scope"] == manifest["identity_scope"] and obj["snapshot_id"] == manifest["snapshot_id"], "OBJECT_CONTEXT_MISMATCH")
            require(set(obj["record_evidence_refs"]) <= evidence.keys(), "OBJECT_EVIDENCE_MISSING")
        resolved, source_cache = {}, {}
        for source in sources.values():
            require(source["availability"] == "EMBEDDED", "SOURCE_NOT_AVAILABLE_FOR_RECHECK")
            raw = self.read(source["path"])
            require(len(raw) == source["bytes"] and hashlib.sha256(raw).hexdigest() == source["sha256"], "SOURCE_HASH_MISMATCH")
            source_cache[source["source_id"]] = raw
        for row in evidence.values():
            require(row["source_id"] in sources, "EVIDENCE_SOURCE_MISSING")
            source = sources[row["source_id"]]
            require(source["availability"] == "EMBEDDED", "SOURCE_NOT_AVAILABLE_FOR_RECHECK")
            raw = source_cache[row["source_id"]]
            require(len(raw) == source["bytes"] and hashlib.sha256(raw).hexdigest() == source["sha256"] == row["source_sha256"], "SOURCE_HASH_MISMATCH")
            require(source["version"] == row["source_version"], "SOURCE_VERSION_MISMATCH")
            if row["locator"]["kind"] == "TEXT_RANGE":
                text, loc = raw.decode("utf-8"), row["locator"]
                require(0 <= loc["start"] < loc["end"] <= len(text) and text[loc["start"]:loc["end"]] == row["quote"], "QUOTE_MISMATCH")
                require(loc["line"] == text[:loc["start"]].count("\n") + 1, "QUOTE_LINE_MISMATCH")
                resolved[row["evidence_id"]] = row["quote"]
            else:
                value = resolve_pointer(json.loads(raw), row["locator"]["pointer"])
                if isinstance(value, dict) and "record_id" in value:
                    require(value["record_id"] == row["locator"]["record_id"], "EVIDENCE_RECORD_ID_MISMATCH")
                resolved[row["evidence_id"]] = value
        check_assertions(self, facts=facts, objects=objects, sources=sources, evidence=evidence,
            assertions=assertions, resolved=resolved, dependencies=dependencies)
        review = self.document("quality/review.json")
        for bound in review["reviewed_artifacts"]:
            require(hashlib.sha256(self.read(bound["path"])).hexdigest() == bound["sha256"], "REVIEW_ARTIFACT_CHANGED")
        profile = self.document("standardization/profile.json")
        require(profile["formal_conformance_claim"] is False and profile["final_text_review_status"] == "PENDING_OFFICIAL_FINAL_FULLTEXT", "UNSUPPORTED_CONFORMANCE_CLAIM")
        require(dependencies["reference_profile"]["sha256"] == hashlib.sha256(self.read("standardization/profile.json")).hexdigest(), "REFERENCE_PROFILE_CHANGED")
        counts = {"classes": len(self.document("model/catalog.json")["classes"]), "properties": len(self.document("model/catalog.json")["properties"]),
            "objects": len(objects), "facts": len(facts), "assertions": len(assertions), "evidence": len(evidence)}
        require(counts == manifest["counts"], "MANIFEST_COUNTS_MISMATCH")
        baseline = self.document("acceptance/baseline.json")
        require(baseline["frozen"] is True, "UNFROZEN_ACCEPTANCE")
        for target in baseline["target_inventory"]:
            require(target["object_id"] in objects and objects[target["object_id"]]["type_iri"] == target["type_iri"], "TARGET_COVERAGE_MISSING")
        query = self.read(baseline["query_ref"]).decode("utf-8")
        operation = assert_read_only_query(query, max_characters=20000, max_path_depth=8)
        require(operation == "SELECT", "V3_BASELINE_SUPPORTS_MULTISET_SELECT_ONLY")
        self.query_graph = self.graphs["ontology"] + self.graphs["instances"]
        # v3 imports may contain OWL blank-node expressions. Native authoritative
        # canonical_nquads intentionally forbids those; use a query-only dataset
        # without changing the original graphs or their hash identities.
        dataset = Dataset()
        business_graph = dataset.graph(URIRef("urn:ontology-delivery:inspection:business"))
        for s, p, o in self.query_graph:
            business_graph.add((s, p, o))
        nquads = dataset.serialize(format="nquads", encoding="utf-8")
        status, result = _execute(nquads, query, operation, query_timeout_seconds, max_query_results)
        require(status == "OK", "QUERY_" + status)
        names = baseline["variables"]
        require(result["variables"] == names, "QUERY_VARIABLES_MISMATCH")
        actual = Counter(tuple(row.get(n) for n in names) for row in result["rows"])
        expected = Counter(tuple(term(row[n]).n3() for n in names) for row in baseline["expected"])
        require(actual == expected, "QUERY_ANSWER_MISMATCH")
        shacl = {"status": "NOT_RUN"}
        if run_shacl:
            require(not any(p in {SH.sparql, SH.js, SH.rule, SH.select, SH.ask} for _, p, _ in self.graphs["shapes"]), "EXECUTABLE_SHACL_PROFILE_UNSUPPORTED")
            shacl = shacl_check(self.graphs)
        return {"status": "PASS" if shacl["status"] in {"NOT_RUN", "PASS"} else shacl["status"], "profile": "V3_READ_ONLY_ENGINEERING_INSPECTION", "package_id": manifest["package_id"],
            "manifest_sha256": hashlib.sha256(self.read("manifest.json")).hexdigest(), "counts": counts,
            "shacl": shacl, "owl": {"status": "NOT_RUN"}, "real_approval": {"status": "NOT_RUN"},
            "semantic_accuracy": None, "production_allowed": False, "release_status": "NOT_RELEASED",
            "limitations": ["References and exact quotes do not prove that evidence supports each fact", "Receipt cannot grant Registry or publication authority"]}


def package_bytes(files):
    """Package a complete v3 file set; does not fabricate missing semantic data."""
    V3Delivery(files).inspect()
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            path_name(name)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return stream.getvalue()
