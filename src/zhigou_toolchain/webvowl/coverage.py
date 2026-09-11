from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..modeling.dependencies import ROOT
from .contracts import validate_webvowl_contract
from .verifier import scan_vowl_leakage

_PROJECT_TERM_PREFIX = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"
_XSD_PREFIX = "http://www.w3.org/2001/XMLSchema#"
_ALLOWED_SUPPORT_IRIS = {
    f"{_XSD_PREFIX}{name}"
    for name in ("string", "integer", "boolean", "date", "dateTime", "decimal")
}
_ALLOWED_SUPPORT_IRIS.add("http://www.w3.org/2002/07/owl#Thing")
_DECLARATION_TYPES = {
    "Class": ("owl:Class", "rdfs:Class"),
    "ObjectProperty": ("owl:objectProperty", "owl:ObjectProperty"),
    "DatatypeProperty": ("owl:datatypeProperty", "owl:DatatypeProperty"),
}


class CoverageError(ValueError):
    pass


def _inventory(root: Path) -> list[dict[str, str]]:
    with (root / "docs/ontology/term-inventory.csv").open(
        encoding="utf-8", newline=""
    ) as f:
        rows = list(csv.DictReader(f))
    return rows


def _annotation_values(item: Mapping[str, Any], name: str) -> set[str]:
    annotations = item.get("annotations")
    if not isinstance(annotations, Mapping):
        return set()
    values = annotations.get(name, [])
    if not isinstance(values, list):
        return set()
    return {
        str(entry["value"])
        for entry in values
        if isinstance(entry, Mapping) and "value" in entry
    }


def _endpoint_iris(value: Any, by_id: Mapping[str, str]) -> set[str]:
    values = value if isinstance(value, list) else [value]
    result: set[str] = set()
    for item in values:
        if item is None:
            continue
        key = str(item)
        result.add(by_id.get(key, key))
    return result


def _expected_endpoint(value: str, by_local: Mapping[str, str]) -> str | None:
    if not value:
        return None
    if value.startswith("xsd:"):
        return _XSD_PREFIX + value.split(":", 1)[1]
    return by_local.get(value, value)


def build_coverage_report(
    vowl: Mapping[str, Any], *, source: Mapping[str, Any], root: Path = ROOT
) -> dict[str, Any]:
    class_attrs = [x for x in vowl.get("classAttribute", []) if isinstance(x, Mapping)]
    property_attrs = [
        x for x in vowl.get("propertyAttribute", []) if isinstance(x, Mapping)
    ]
    attrs = class_attrs + property_attrs
    by_iri: dict[str, Mapping[str, Any]] = {}
    duplicate_iris: set[str] = set()
    malformed_anonymous: set[str] = set()
    for item in attrs:
        iri = item.get("iri")
        if not iri:
            markers = {str(value) for value in item.get("attributes", [])}
            if "anonymous" not in markers:
                malformed_anonymous.add(str(item.get("id", "<missing-id>")))
            continue
        key = str(iri)
        if key in by_iri:
            # OWL2VOWL may emit one support datatype node per range edge;
            # repeated project term IRIs are still a semantic corruption.
            if key not in _ALLOWED_SUPPORT_IRIS:
                duplicate_iris.add(key)
        else:
            by_iri[key] = item
    class_declarations = {
        str(item.get("id")): str(item.get("type"))
        for item in vowl.get("class", [])
        if isinstance(item, Mapping) and item.get("id") is not None
    }
    property_declarations = {
        str(item.get("id")): str(item.get("type"))
        for item in vowl.get("property", [])
        if isinstance(item, Mapping) and item.get("id") is not None
    }
    class_by_id = {
        str(item.get("id")): str(item.get("iri"))
        for item in class_attrs
        if item.get("id") is not None and item.get("iri")
    }
    baseline = source["baseline"]
    inventory = _inventory(root)
    by_local = {
        str(row.get("local_name", "")): str(row.get("term_iri", ""))
        for row in inventory
        if row.get("local_name") and row.get("term_iri")
    }
    expected = []
    missing = []
    unexpected = []
    semantic_mismatches: set[str] = set(duplicate_iris)
    semantic_mismatches.update(
        f"anonymous-node:{value}" for value in malformed_anonymous
    )
    non_visualized_project_terms: set[str] = set()
    unexpected_external_terms: set[str] = set()
    for row in inventory:
        typ = str(row.get("term_type", ""))
        required = typ in {"Class", "ObjectProperty", "DatatypeProperty"}
        record = {
            "iri": str(row.get("term_iri", "")),
            "ontology_module": str(row.get("defining_module", "")),
            "term_type": typ,
            "expected_labels": [
                x
                for x in (str(row.get("label_en", "")), str(row.get("label_zh_cn", "")))
                if x
            ],
            "required": required,
        }
        expected.append(record)
        actual = by_iri.get(record["iri"])
        if required and actual is None:
            missing.append(record["iri"])
            continue
        if actual is None:
            continue
        if not required:
            non_visualized_project_terms.add(record["iri"])
            continue

        expected_group = "class" if typ == "Class" else "property"
        actual_group = "class" if actual in class_attrs else "property"
        if actual_group != expected_group:
            semantic_mismatches.add(f"{record['iri']}:declaration-group")
        declarations = (
            class_declarations if expected_group == "class" else property_declarations
        )
        actual_type = declarations.get(str(actual.get("id")))
        if actual_type not in _DECLARATION_TYPES[typ]:
            semantic_mismatches.add(f"{record['iri']}:term-type")
        labels = actual.get("label")
        if not isinstance(labels, Mapping):
            semantic_mismatches.add(f"{record['iri']}:labels")
        else:
            for language, expected_label in (
                ("en", str(row.get("label_en", ""))),
                ("zh-cn", str(row.get("label_zh_cn", ""))),
            ):
                if expected_label and labels.get(language) != expected_label:
                    semantic_mismatches.add(f"{record['iri']}:label-{language}")
        if str(row.get("defining_module", "")) not in _annotation_values(
            actual, "definingModule"
        ):
            semantic_mismatches.add(f"{record['iri']}:ontology-module")
        if typ == "Class":
            actual_supers = _endpoint_iris(actual.get("superClasses", []), class_by_id)
            expected_super = _expected_endpoint(
                str(row.get("superclass", "")), by_local
            )
            expected_supers = {expected_super} if expected_super else set()
            if actual_supers != expected_supers:
                semantic_mismatches.add(f"{record['iri']}:class-hierarchy")
        else:
            for field in ("domain", "range"):
                expected_endpoint = _expected_endpoint(
                    str(row.get(field, "")), by_local
                )
                actual_endpoints = _endpoint_iris(actual.get(field), class_by_id)
                expected_endpoints = {expected_endpoint} if expected_endpoint else set()
                implicit_thing = {"http://www.w3.org/2002/07/owl#Thing"}
                if expected_endpoint:
                    matches = actual_endpoints == expected_endpoints
                else:
                    matches = actual_endpoints in (set(), implicit_thing)
                if not matches:
                    semantic_mismatches.add(f"{record['iri']}:{field}")
    project_iris = {str(x["iri"]) for x in expected}
    for iri, item in by_iri.items():
        if (
            iri.startswith("https://yangjunjie-lin.github.io/KG-MNP-Demo/")
            and iri not in project_iris
        ):
            unexpected.append(iri)
        elif iri not in project_iris and iri not in _ALLOWED_SUPPORT_IRIS:
            unexpected_external_terms.add(iri)
    header = vowl.get("header")
    if not isinstance(header, Mapping):
        semantic_mismatches.add("header:missing")
    else:
        if str(header.get("iri", "")) != str(baseline.get("root_ontology_iri", "")):
            semantic_mismatches.add("header:iri")
        if str(header.get("version", "")) != str(baseline.get("ontology_version", "")):
            semantic_mismatches.add("header:version")
        other = header.get("other")
        version_info = (
            other.get("versionInfo", []) if isinstance(other, Mapping) else []
        )
        values = {
            str(item.get("value"))
            for item in version_info
            if isinstance(item, Mapping) and item.get("value") is not None
        }
        if values and str(baseline.get("ontology_version", "")) not in values:
            semantic_mismatches.add("header:versionInfo")
        for base in (
            header.get("baseIris", [])
            if isinstance(header.get("baseIris"), list)
            else []
        ):
            if str(base).startswith(_PROJECT_TERM_PREFIX) and str(
                base
            ) != _PROJECT_TERM_PREFIX.rstrip("#"):
                semantic_mismatches.add(f"header:unexpected-base:{base}")
    represented = []
    for item in expected:
        actual = by_iri.get(item["iri"])
        represented.append(
            {
                **item,
                "represented": actual is not None,
                "vowl_internal_id": str(actual.get("id"))
                if actual is not None
                else None,
            }
        )
    # Coverage is not limited to node IRI fields: runtime/ABox content hidden
    # in headers, annotations, labels, or arbitrary nested JSON must fail too.
    leakage = scan_vowl_leakage(vowl)
    report = {
        "contract_version": "1.0",
        "expected": expected,
        "represented": represented,
        "missing_required_terms": sorted(missing),
        "unexpected_project_terms": sorted(unexpected),
        "non_visualized_project_terms": sorted(non_visualized_project_terms),
        "unexpected_external_terms": sorted(unexpected_external_terms),
        "semantic_mismatches": sorted(semantic_mismatches),
        "abox_leakage_hits": leakage["hits"],
        "status": "PASS"
        if not missing
        and not unexpected
        and not non_visualized_project_terms
        and not unexpected_external_terms
        and not semantic_mismatches
        and leakage["status"] == "PASS"
        else "FAILED",
    }
    validate_webvowl_contract("coverage-report", report, root)
    return report


def build_representation_loss(
    vowl: Mapping[str, Any], *, source: Mapping[str, Any], root: Path = ROOT
) -> dict[str, Any]:
    from rdflib import BNode, URIRef
    from rdflib.namespace import OWL, RDF, RDFS

    graphs = source["graphs"]
    direct = {
        "Class": sum(
            1
            for q in graphs
            if q[1] == URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
            and q[2] in (OWL.Class, RDFS.Class)
        ),
        "ObjectProperty": sum(
            1
            for q in graphs
            if q[1] == URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
            and q[2] == OWL.ObjectProperty
        ),
        "DatatypeProperty": sum(
            1
            for q in graphs
            if q[1] == URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
            and q[2] == OWL.DatatypeProperty
        ),
    }
    restrictions = sum(
        1
        for q in graphs
        if q[1] == RDF.type and q[2] == OWL.Restriction and isinstance(q[0], BNode)
    )
    characteristics = {
        OWL.FunctionalProperty,
        OWL.InverseFunctionalProperty,
        OWL.SymmetricProperty,
        OWL.AsymmetricProperty,
        OWL.TransitiveProperty,
        OWL.ReflexiveProperty,
        OWL.IrreflexiveProperty,
    }
    counts = {
        "AnnotationProperty": sum(
            1 for q in graphs if q[1] == RDF.type and q[2] == OWL.AnnotationProperty
        ),
        "PropertyCharacteristics": sum(
            1 for q in graphs if q[1] == RDF.type and q[2] in characteristics
        ),
        "AxiomAnnotations": sum(
            1 for q in graphs if q[1] == RDF.type and q[2] == OWL.Axiom
        ),
        "Disjointness": sum(
            1
            for q in graphs
            if q[1] == OWL.disjointWith
            or (q[1] == RDF.type and q[2] == OWL.AllDisjointClasses)
        ),
        "Equivalence": sum(
            1 for q in graphs if q[1] in (OWL.equivalentClass, OWL.equivalentProperty)
        ),
        "ImportsAndVersionMetadata": sum(
            1 for q in graphs if q[1] in (OWL.imports, OWL.versionIRI, OWL.versionInfo)
        ),
    }
    class_attrs = [
        item for item in vowl.get("classAttribute", []) if isinstance(item, Mapping)
    ]
    property_attrs = [
        item for item in vowl.get("propertyAttribute", []) if isinstance(item, Mapping)
    ]
    represented_iris = {
        str(item["iri"]) for item in class_attrs + property_attrs if item.get("iri")
    }
    formal_iris = {
        "Class": {
            str(q[0])
            for q in graphs
            if q[1] == RDF.type and q[2] in (OWL.Class, RDFS.Class)
        },
        "ObjectProperty": {
            str(q[0]) for q in graphs if q[1] == RDF.type and q[2] == OWL.ObjectProperty
        },
        "DatatypeProperty": {
            str(q[0])
            for q in graphs
            if q[1] == RDF.type and q[2] == OWL.DatatypeProperty
        },
    }
    anonymous_rendered = sum(
        "anonymous" in {str(value) for value in item.get("attributes", [])}
        for item in property_attrs
    )
    annotation_rendered = any(
        bool(item.get("annotations")) for item in class_attrs + property_attrs
    )
    axiom_annotation_rendered = any(
        key.lower().replace("_", "") in {"axiomannotation", "axiomannotations"}
        for item in class_attrs + property_attrs
        for key in item
    )
    disjoint_rendered = any(
        str(item.get("type", "")) == "owl:disjointWith"
        for item in vowl.get("property", [])
        if isinstance(item, Mapping)
    ) or any(
        key.lower() in {"disjoint", "disjointwith", "disjointunion"}
        for item in class_attrs + property_attrs
        for key in item
    )
    equivalence_rendered = any(
        key.lower() in {"equivalent", "equivalentclass", "equivalentproperty"}
        for item in class_attrs + property_attrs
        for key in item
    )
    characteristic_markers = {
        OWL.FunctionalProperty: "functional",
        OWL.InverseFunctionalProperty: "inverse-functional",
        OWL.SymmetricProperty: "symmetric",
        OWL.AsymmetricProperty: "asymmetric",
        OWL.TransitiveProperty: "transitive",
        OWL.ReflexiveProperty: "reflexive",
        OWL.IrreflexiveProperty: "irreflexive",
    }
    characteristic_support = True
    formal_characteristics = [
        q for q in graphs if q[1] == RDF.type and q[2] in characteristics
    ]
    for subject, _, characteristic, *_ in formal_characteristics:
        marker = characteristic_markers[characteristic]
        actual = next(
            (item for item in property_attrs if str(item.get("iri")) == str(subject)),
            None,
        )
        if actual is None or marker not in {
            str(value) for value in actual.get("attributes", [])
        }:
            characteristic_support = False
            break

    def direct_status(kind: str, count: int) -> tuple[str, str]:
        if count and formal_iris[kind] <= represented_iris:
            return (
                "DIRECT",
                "Named OWL terms are present in the corresponding VOWL projection nodes.",
            )
        return (
            "NOT_VISUALIZED",
            "One or more formal named terms are absent from the VOWL projection.",
        )

    def indirect_status(
        count: int, supported: bool, direct_reason: str, absent_reason: str
    ) -> tuple[str, str]:
        if count and supported:
            return "INDIRECT", direct_reason
        return "NOT_VISUALIZED", absent_reason

    class_status, class_reason = direct_status("Class", direct["Class"])
    object_status, object_reason = direct_status(
        "ObjectProperty", direct["ObjectProperty"]
    )
    datatype_status, datatype_reason = direct_status(
        "DatatypeProperty", direct["DatatypeProperty"]
    )
    annotation_status, annotation_reason = indirect_status(
        counts["AnnotationProperty"],
        annotation_rendered,
        "Annotation values are retained in VOWL metadata without becoming required term nodes.",
        "The frozen VOWL output contains no annotation-property representation.",
    )
    restriction_status, restriction_reason = indirect_status(
        restrictions,
        anonymous_rendered >= restrictions,
        "Anonymous OWL restrictions are represented only through anonymous VOWL edges.",
        "Anonymous OWL restrictions have no representation in the frozen VOWL output.",
    )
    characteristic_status, characteristic_reason = indirect_status(
        counts["PropertyCharacteristics"],
        characteristic_support,
        "Property characteristic markers are retained on VOWL property attributes.",
        "Property characteristics are absent from the frozen VOWL output.",
    )
    axiom_status, axiom_reason = indirect_status(
        counts["AxiomAnnotations"],
        axiom_annotation_rendered,
        "Axiom annotation metadata is retained in the VOWL output.",
        "Axiom annotations have no representation in the frozen VOWL output.",
    )
    disjoint_status, disjoint_reason = indirect_status(
        counts["Disjointness"],
        disjoint_rendered,
        "Disjointness is represented by VOWL disjoint relation declarations.",
        "Disjointness has no representation in the frozen VOWL output.",
    )
    equivalence_status, equivalence_reason = indirect_status(
        counts["Equivalence"],
        equivalence_rendered,
        "Equivalence relations are retained as VOWL relation metadata.",
        "Equivalence has no representation in the frozen VOWL output.",
    )
    metadata = vowl.get("header")
    metadata_rendered = isinstance(metadata, Mapping) and bool(
        metadata.get("iri") or metadata.get("version") or metadata.get("other")
    )
    metadata_status, metadata_reason = indirect_status(
        counts["ImportsAndVersionMetadata"],
        metadata_rendered,
        "Import and version metadata are retained in the VOWL header.",
        "Import and version metadata have no representation in the frozen VOWL output.",
    )
    records = [
        {
            "owl_construct": "Class",
            "formal_count": direct["Class"],
            "representation_status": class_status,
            "reason": class_reason,
        },
        {
            "owl_construct": "ObjectProperty",
            "formal_count": direct["ObjectProperty"],
            "representation_status": object_status,
            "reason": object_reason,
        },
        {
            "owl_construct": "DatatypeProperty",
            "formal_count": direct["DatatypeProperty"],
            "representation_status": datatype_status,
            "reason": datatype_reason,
        },
        {
            "owl_construct": "AnnotationProperty",
            "formal_count": counts["AnnotationProperty"],
            "representation_status": annotation_status,
            "reason": annotation_reason,
        },
        {
            "owl_construct": "AnonymousRestrictions",
            "formal_count": restrictions,
            "representation_status": restriction_status,
            "reason": restriction_reason,
        },
        {
            "owl_construct": "PropertyCharacteristics",
            "formal_count": counts["PropertyCharacteristics"],
            "representation_status": characteristic_status,
            "reason": characteristic_reason,
        },
        {
            "owl_construct": "AxiomAnnotations",
            "formal_count": counts["AxiomAnnotations"],
            "representation_status": axiom_status,
            "reason": axiom_reason,
        },
        {
            "owl_construct": "Disjointness",
            "formal_count": counts["Disjointness"],
            "representation_status": disjoint_status,
            "reason": disjoint_reason,
        },
        {
            "owl_construct": "Equivalence",
            "formal_count": counts["Equivalence"],
            "representation_status": equivalence_status,
            "reason": equivalence_reason,
        },
        {
            "owl_construct": "ImportsAndVersionMetadata",
            "formal_count": counts["ImportsAndVersionMetadata"],
            "representation_status": metadata_status,
            "reason": metadata_reason,
        },
    ]
    report = {
        "contract_version": "1.0",
        "constructs": records,
        "status": (
            "PASS"
            if all(
                status == "DIRECT"
                for status in (class_status, object_status, datatype_status)
            )
            else "FAILED"
        ),
    }
    validate_webvowl_contract("representation-loss", report, root)
    return report
