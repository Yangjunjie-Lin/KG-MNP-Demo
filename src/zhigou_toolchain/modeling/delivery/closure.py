"""Cross-file checks over the actual v3 RDF and source snapshots.

These checks establish referential and deterministic mapping consistency, not
the truth of business statements or the authority of an imported review.
"""
from __future__ import annotations

import re

from rdflib import OWL, RDF, RDFS, SH, Literal, URIRef

from .v3 import DeliveryError, require


def resolve_pointer(value, pointer):
    for segment in pointer.split("/")[1:]:
        require(re.search(r"~(?![01])", segment) is None, "INVALID_JSON_POINTER_ESCAPE")
        key = segment.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            require(re.fullmatch(r"0|[1-9][0-9]*", key) is not None and int(key) < len(value), "JSON_POINTER_INDEX_INVALID")
            value = value[int(key)]
        else:
            require(isinstance(value, dict) and key in value, "JSON_POINTER_KEY_MISSING")
            value = value[key]
    return value


def check_catalog(delivery):
    from .v3 import _unique

    graph, shapes = delivery.graphs["ontology"], delivery.graphs["shapes"]
    catalog = delivery.document("model/catalog.json")
    classes = _unique(catalog["classes"], "iri")
    properties = _unique(catalog["properties"], "iri")
    rules = _unique(delivery.document("model/rules.json")["items"], "rule_id")
    for row in classes.values():
        subject = URIRef(row["iri"])
        require((subject, RDF.type, OWL.Class) in graph, "CATALOG_CLASS_NOT_IN_RDF")
        require(row["identifier_property"] in properties and row["label_property"] in properties, "CLASS_PROPERTY_NOT_IN_CATALOG")
        require((URIRef(row["shape_iri"]), SH.targetClass, subject) in shapes, "CATALOG_SHAPE_TARGET_MISMATCH")
    for row in properties.values():
        subject = URIRef(row["iri"])
        require((subject, RDF.type, OWL[row["kind"]]) in graph, "CATALOG_PROPERTY_TYPE_MISMATCH")
        require((subject, RDFS.domain, URIRef(row["domain"])) in graph
            and (subject, RDFS.range, URIRef(row["range"])) in graph, "CATALOG_DOMAIN_RANGE_MISMATCH")
        require(row["rule_ref"] in rules, "CATALOG_RULE_REFERENCE_MISSING")
    terms = _unique(delivery.document("model/terms.json")["items"], "iri")
    require(set(terms) == set(classes) | set(properties), "TERM_CATALOG_INVENTORY_MISMATCH")
    for row in terms.values():
        subject = URIRef(row["iri"])
        require((subject, RDF.type, OWL[row["kind"]]) in graph, "TERM_TYPE_NOT_IN_RDF")
        require(set(row["property_refs"]) <= properties.keys() and set(row["constraint_refs"]) <= rules.keys(), "TERM_REFERENCE_MISSING")
        for key, predicate in (("domain", RDFS.domain), ("range", RDFS.range)):
            if row[key] is not None:
                require((subject, predicate, URIRef(row[key])) in graph, "TERM_DOMAIN_RANGE_NOT_IN_RDF")
        for label in row["labels"]:
            require((subject, RDFS.label, Literal(label["value"], lang=label["language"])) in graph, "TERM_LABEL_NOT_IN_RDF")
    axioms = _unique(delivery.document("model/axioms.json")["items"], "axiom_id")
    for row in axioms.values():
        require((URIRef(row["subject"]), URIRef(row["predicate"]), URIRef(row["object"])) in graph, "AXIOM_NOT_IN_RDF")
        expected = {"DECLARATION": RDF.type, "DOMAIN": RDFS.domain, "RANGE": RDFS.range}[row["kind"]]
        require(row["predicate"] == str(expected), "AXIOM_KIND_MISMATCH")
        delivery.read(row["basis_ref"])
    return classes, properties


def check_assertions(delivery, *, facts, objects, sources, evidence, assertions, resolved, dependencies):
    from .v3 import _unique

    mapping = delivery.document("mapping/mapping.json")
    rules = _unique(mapping["fact_rules"], "id")
    entities = _unique(mapping["entity_rules"], "id")
    require(not (rules.keys() & entities.keys()), "MAPPING_RULE_ID_COLLISION")
    transforms = {row["id"] + "@" + row["version"] for row in dependencies["transforms"]}
    for rule in [*rules.values(), *entities.values()]:
        for key in ("source_id", "target_source_id"):
            if key in rule:
                require(rule[key] in sources, "MAPPING_SOURCE_MISSING")
    for assertion in assertions.values():
        require(assertion["fact_id"] in facts and assertion["evidence_ref"] in evidence, "ORPHAN_ASSERTION")
        fact = facts[assertion["fact_id"]]
        require(assertion["assertion_id"] in fact["assertion_refs"], "ORPHAN_ASSERTION")
        require(assertion["mapping_rule_id"] in rules, "ASSERTION_MAPPING_RULE_MISSING")
        require(assertion["transform_id"] in transforms, "ASSERTION_TRANSFORM_NOT_LOCKED")
        rule = rules[assertion["mapping_rule_id"]]
        if "transform_id" in rule:
            require(rule["transform_id"] == assertion["transform_id"], "ASSERTION_TRANSFORM_MISMATCH")
        if "source_id" in rule:
            require(rule["source_id"] == assertion["source_id"], "ASSERTION_MAPPING_SOURCE_MISMATCH")
        # v3 facts have no negative/conditional assertion semantics. Refuse to
        # silently collapse those statements into positive default-graph facts.
        require(assertion["polarity"] == "POSITIVE" and not assertion["conditional"], "NON_POSITIVE_ASSERTION_CANNOT_SUPPORT_FACT")
        value = resolved[assertion["evidence_ref"]]
        operation = rule["operation"]
        candidates = [r for r in entities.values() if r["source_id"] == assertion["source_id"]]
        if operation == "ASSERT_TYPE":
            require(fact["predicate"] == str(RDF.type) and fact["object"]["type"] == "iri", "MAPPING_TYPE_FACT_MISMATCH")
            require(any(r["type_iri"] == fact["object"]["value"] for r in candidates), "MAPPING_ENTITY_TYPE_MISMATCH")
        elif operation == "COPY_STRING":
            field = assertion["source_field"]
            require(isinstance(value, dict) and field in value and isinstance(value[field], str), "MAPPING_SOURCE_FIELD_MISSING")
            require(any(r["attributes"].get(field) == fact["predicate"] for r in candidates), "MAPPING_ATTRIBUTE_PREDICATE_MISMATCH")
            require(fact["object"]["type"] == "literal" and fact["object"]["value"] == value[field], "MAPPING_LITERAL_VALUE_MISMATCH")
        elif operation == "LOOKUP_OBJECT":
            require(fact["predicate"] == rule.get("predicate") and fact["object"]["type"] == "iri", "MAPPING_RELATION_MISMATCH")
            require(assertion["source_field"] == rule.get("source_field") and isinstance(value, dict)
                and assertion["source_field"] in value, "MAPPING_SOURCE_FIELD_MISSING")
            target = objects.get(fact["object"]["value"])
            if target is None:
                raise DeliveryError("MAPPING_LOOKUP_TARGET_MISMATCH")
            require(target["business_id"] == value[assertion["source_field"]], "MAPPING_LOOKUP_TARGET_MISMATCH")
            require(any(evidence[e]["source_id"] == rule["target_source_id"] and isinstance(resolved[e], dict)
                and resolved[e].get(rule["target_field"]) == target["business_id"] for e in target["record_evidence_refs"]), "MAPPING_LOOKUP_SOURCE_MISMATCH")
        else:
            require(fact["predicate"] == rule.get("predicate") and isinstance(value, str), "MAPPING_TEXT_RELATION_MISMATCH")
            # Do not execute a template as arbitrary code or claim linguistic
            # entailment from matching quote coordinates alone.
            require(assertion["source_field"] is None, "TEXT_ASSERTION_SOURCE_FIELD_UNSUPPORTED")
    for fact in facts.values():
        require(fact["subject"] in objects, "FACT_SUBJECT_NOT_REGISTERED")
        require(set(fact["evidence_refs"]) == {assertions[a]["evidence_ref"] for a in fact["assertion_refs"]}, "FACT_EVIDENCE_CLOSURE_MISMATCH")
        if fact["predicate"] != str(RDF.type) and fact["object"]["type"] == "iri":
            require(fact["object"]["value"] in objects, "FACT_RELATION_TARGET_NOT_REGISTERED")
    classes, _properties = check_catalog(delivery)
    for obj in objects.values():
        require(obj["type_iri"] in classes, "OBJECT_TYPE_NOT_IN_CATALOG")
        row = classes[obj["type_iri"]]
        graph = delivery.graphs["instances"]
        require(any(str(v) == obj["business_id"] for v in graph.objects(URIRef(obj["object_id"]), URIRef(row["identifier_property"]))), "OBJECT_IDENTIFIER_MISMATCH")
        require(any(str(v) == obj["label"] for v in graph.objects(URIRef(obj["object_id"]), URIRef(row["label_property"]))), "OBJECT_LABEL_MISMATCH")
