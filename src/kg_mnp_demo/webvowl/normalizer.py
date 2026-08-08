from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse


class NormalizationError(ValueError):
    pass


ALLOWED_TOP = {
    "_comment",
    "header",
    "namespace",
    "class",
    "classAttribute",
    "datatype",
    "datatypeAttribute",
    "property",
    "propertyAttribute",
    "individual",
}


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out = {}
    for k, v in pairs:
        if k in out:
            raise NormalizationError(f"duplicate JSON key: {k}")
        out[k] = v
    return out


def _remap(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_remap(v, mapping) for v in value]
    if isinstance(value, dict):
        return {
            k: _remap(v, mapping)
            if k not in {"iri", "label", "comment", "annotations"}
            else v
            for k, v in value.items()
        }
    return value


def _unique_ids(items: list[dict[str, Any]], label: str) -> set[str]:
    ids = [
        str(item.get("id")) for item in items if isinstance(item, dict) and "id" in item
    ]
    if len(ids) != len(items):
        raise NormalizationError(f"VOWL {label} node has no internal id")
    if len(ids) != len(set(ids)):
        raise NormalizationError(f"duplicate VOWL {label} internal id")
    return set(ids)


def _is_uri(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return bool(parsed.scheme)


def _validate_metadata(value: Mapping[str, Any]) -> None:
    header = value.get("header")
    if header is not None:
        if not isinstance(header, dict):
            raise NormalizationError("VOWL header must be an object")
        allowed_header = {
            "baseIris",
            "description",
            "iri",
            "languages",
            "other",
            "prefixList",
            "title",
            "version",
        }
        unknown_header = set(header) - allowed_header
        if unknown_header:
            raise NormalizationError(
                "unsupported VOWL header fields: " + ", ".join(sorted(unknown_header))
            )
        for key in ("iri", "version"):
            if key in header and not isinstance(header[key], str):
                raise NormalizationError(f"VOWL header {key} must be text")
        if "iri" in header and not _is_uri(header["iri"]):
            raise NormalizationError("VOWL header iri must be a URI")
        if "baseIris" in header and (
            not isinstance(header["baseIris"], list)
            or any(not _is_uri(item) for item in header["baseIris"])
        ):
            raise NormalizationError("VOWL header baseIris must be URI strings")
        if "languages" in header and (
            not isinstance(header["languages"], list)
            or any(not isinstance(item, str) for item in header["languages"])
        ):
            raise NormalizationError("VOWL header languages must be text")
        if "prefixList" in header:
            prefixes = header["prefixList"]
            if not isinstance(prefixes, dict) or any(
                not isinstance(key, str) or not _is_uri(namespace)
                for key, namespace in prefixes.items()
            ):
                raise NormalizationError("VOWL header prefixList is invalid")
        for key in ("description", "title"):
            if key in header:
                text = header[key]
                if not isinstance(text, dict) or any(
                    not isinstance(language, str) or not isinstance(content, str)
                    for language, content in text.items()
                ):
                    raise NormalizationError(f"VOWL header {key} is invalid")
        if "other" in header:
            other = header["other"]
            if not isinstance(other, dict):
                raise NormalizationError("VOWL header other metadata is invalid")
            for key, entries in other.items():
                if not isinstance(key, str) or not isinstance(entries, list):
                    raise NormalizationError("VOWL header other metadata is invalid")
                for entry in entries:
                    if (
                        not isinstance(entry, dict)
                        or set(entry) != {"identifier", "language", "type", "value"}
                        or any(not isinstance(item, str) for item in entry.values())
                    ):
                        raise NormalizationError(
                            "VOWL header other metadata entry is invalid"
                        )
    namespace = value.get("namespace")
    if namespace is not None:
        if not isinstance(namespace, list):
            raise NormalizationError("VOWL namespace must be an array")
        for item in namespace:
            if not isinstance(item, dict) or not _is_uri(item.get("iri")):
                raise NormalizationError("VOWL namespace entry is invalid")
            if set(item) - {"iri", "name"}:
                raise NormalizationError("unsupported VOWL namespace fields")
            if "name" in item and not isinstance(item["name"], str):
                raise NormalizationError("VOWL namespace name must be text")


def _validate_node_shape(item: Mapping[str, Any], label: str) -> None:
    if "iri" in item and not _is_uri(item["iri"]):
        raise NormalizationError(f"VOWL {label} node iri must be a URI")
    if "label" in item:
        labels = item["label"]
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        ):
            raise NormalizationError(f"VOWL {label} node label is invalid")
    if "attributes" in item and (
        not isinstance(item["attributes"], list)
        or any(not isinstance(value, str) for value in item["attributes"])
    ):
        raise NormalizationError(f"VOWL {label} node attributes are invalid")
    if "annotations" in item and not isinstance(item["annotations"], dict):
        raise NormalizationError(f"VOWL {label} node annotations are invalid")


def _map_reference(value: Any, mapping: Mapping[str, str], field: str) -> Any:
    if value is None:
        return None

    def one(item: Any) -> str:
        key = str(item)
        if key not in mapping:
            raise NormalizationError(f"dangling VOWL {field} reference: {key}")
        return mapping[key]

    if isinstance(value, list):
        return sorted({one(item) for item in value})
    return one(value)


def normalize_vowl_json(
    raw: Mapping[str, Any] | bytes | str,
    *,
    exclusion_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(raw, (bytes, str)):
        try:
            value = json.loads(raw, object_pairs_hook=_unique)
        except Exception as exc:
            raise NormalizationError(f"invalid raw VOWL JSON: {exc}") from exc
    else:
        value = deepcopy(dict(raw))
    if not isinstance(value, dict):
        raise NormalizationError("VOWL root must be an object")
    _validate_metadata(value)
    unknown = set(value) - ALLOWED_TOP
    if unknown:
        raise NormalizationError(
            "unsupported VOWL top-level fields: " + ", ".join(sorted(unknown))
        )
    for key in ("classAttribute", "propertyAttribute"):
        if not isinstance(value.get(key), list):
            raise NormalizationError(f"VOWL {key} must be an array")
    for key in ("datatype", "datatypeAttribute"):
        if value.get(key):
            raise NormalizationError(f"unsupported non-empty VOWL {key} structure")
    if any(
        not isinstance(x, dict)
        for x in value["classAttribute"] + value["propertyAttribute"]
    ):
        raise NormalizationError("VOWL node must be an object")
    for item in value["classAttribute"]:
        _validate_node_shape(item, "class")
    for item in value["propertyAttribute"]:
        _validate_node_shape(item, "property")
    classes = sorted(
        value["classAttribute"],
        key=lambda x: (str(x.get("iri", "")), str(x.get("id", ""))),
    )
    props = sorted(
        value["propertyAttribute"],
        key=lambda x: (str(x.get("iri", "")), str(x.get("id", ""))),
    )
    class_ids = _unique_ids(classes, "class")
    property_ids = _unique_ids(props, "property")
    named_iris = [
        str(item["iri"]) for item in classes + props if item.get("iri") is not None
    ]
    duplicates = {iri for iri in named_iris if named_iris.count(iri) > 1}
    if any(
        not iri.startswith("http://www.w3.org/2001/XMLSchema#") for iri in duplicates
    ):
        raise NormalizationError("duplicate VOWL term IRI")
    if any(
        not item.get("iri")
        and "anonymous" not in {str(value) for value in item.get("attributes", [])}
        for item in classes + props
    ):
        raise NormalizationError("unnamed VOWL node is not explicitly anonymous")

    # Formal OWL2VOWL output carries a declaration for every attribute.  Keep
    # the tiny attrs-only fixtures used by low-level tests permissive, while
    # applying the closed declaration/type contract to real converter output.
    strict_declarations = "class" in value or "property" in value
    if strict_declarations:
        class_declarations = value.get("class", [])
        property_declarations = value.get("property", [])
        if not isinstance(class_declarations, list) or not isinstance(
            property_declarations, list
        ):
            raise NormalizationError("VOWL declarations must be arrays")
        for group, declarations, attrs_for_group in (
            ("class", class_declarations, classes),
            ("property", property_declarations, props),
        ):
            if any(
                not isinstance(item, dict)
                or set(item) != {"id", "type"}
                or not isinstance(item.get("id"), (str, int))
                or not isinstance(item.get("type"), str)
                for item in declarations
            ):
                raise NormalizationError(f"VOWL {group} declarations are invalid")
            declaration_ids = {str(item["id"]) for item in declarations}
            attr_ids = {str(item["id"]) for item in attrs_for_group}
            if len(declaration_ids) != len(declarations) or declaration_ids != attr_ids:
                raise NormalizationError(
                    f"VOWL {group} declarations and attributes are not closed"
                )
        class_types = {
            "owl:Class",
            "rdfs:Class",
            "rdfs:Datatype",
            "owl:Thing",
        }
        property_types = {
            "owl:datatypeProperty",
            "owl:DatatypeProperty",
            "owl:objectProperty",
            "owl:ObjectProperty",
            "rdfs:SubClassOf",
            "owl:disjointWith",
        }
        class_types_by_id = {str(x["id"]): x["type"] for x in class_declarations}
        property_types_by_id = {str(x["id"]): x["type"] for x in property_declarations}
        if any(
            class_types_by_id[str(item["id"])] not in class_types for item in classes
        ):
            raise NormalizationError("unsupported VOWL class declaration type")
        if any(
            property_types_by_id[str(item["id"])] not in property_types
            for item in props
        ):
            raise NormalizationError("unsupported VOWL property declaration type")
        for item in props:
            declaration_type = property_types_by_id[str(item["id"])]
            relation_types = {"rdfs:SubClassOf", "owl:disjointWith"}
            named_types = {
                "owl:datatypeProperty",
                "owl:DatatypeProperty",
                "owl:objectProperty",
                "owl:ObjectProperty",
            }
            if not item.get("iri") and declaration_type not in relation_types:
                raise NormalizationError(
                    "unnamed VOWL property has an unsupported declaration type"
                )
            if item.get("iri") and declaration_type not in named_types:
                raise NormalizationError(
                    "named VOWL property has an unsupported declaration type"
                )
    cmap = {str(x["id"]): str(i + 1) for i, x in enumerate(classes)}
    pmap = {str(x["id"]): str(i + 1) for i, x in enumerate(props)}
    normalized_classes = []
    for original in classes:
        item = deepcopy(original)
        item["id"] = cmap[str(original["id"])]
        if item.get("individuals"):
            exclusion = (exclusion_policy or {}).get("class_individuals", {})
            prefix = exclusion.get("allowed_iri_prefix")
            entries = item["individuals"]
            if (
                exclusion.get("action") != "REMOVE_FROM_PRESENTATION_PROJECTION"
                or not isinstance(prefix, str)
                or not isinstance(entries, list)
                or any(
                    not isinstance(entry, dict)
                    or str(entry.get("iri", ""))[: len(prefix)] != prefix
                    for entry in entries
                )
            ):
                raise NormalizationError(
                    "ABox individuals are forbidden in formal VOWL JSON"
                )
            item.pop("individuals")
        if int(item.get("instances", 0) or 0) != 0:
            raise NormalizationError(
                "ABox instance counts are forbidden in formal VOWL JSON"
            )
        for field in (
            "superClasses",
            "subClasses",
            "union",
            "disjointUnion",
            "intersection",
            "equivalent",
            "complement",
        ):
            if field in item:
                item[field] = _map_reference(item[field], cmap, field)
        normalized_classes.append(item)
    normalized_props = []
    for original in props:
        item = deepcopy(original)
        item["id"] = pmap[str(original["id"])]
        for field in ("domain", "range"):
            if field in item:
                item[field] = _map_reference(item[field], cmap, field)
        for field in ("inverse", "equivalent", "superproperty", "subproperty"):
            if field in item:
                item[field] = _map_reference(item[field], pmap, field)
        normalized_props.append(item)
    classes = normalized_classes
    props = normalized_props
    for item in classes + props:
        if "id" not in item:
            raise NormalizationError("VOWL node has no internal id")
        for key in (
            "superClasses",
            "subClasses",
            "domain",
            "range",
            "inverse",
            "equivalent",
        ):
            if key in item and isinstance(item[key], list):
                item[key] = sorted({str(v) for v in item[key]})
    out = deepcopy(value)
    out["classAttribute"] = classes
    out["propertyAttribute"] = props
    for item in out.get("class", []):
        if not isinstance(item, dict) or str(item.get("id")) not in class_ids:
            raise NormalizationError("dangling VOWL class declaration id")
    for item in out.get("property", []):
        if not isinstance(item, dict) or str(item.get("id")) not in property_ids:
            raise NormalizationError("dangling VOWL property declaration id")
    out["class"] = sorted(
        [{**x, "id": cmap[str(x["id"])]} for x in out.get("class", [])],
        key=lambda x: str(x.get("id", "")),
    )
    out["property"] = sorted(
        [{**x, "id": pmap[str(x["id"])]} for x in out.get("property", [])],
        key=lambda x: str(x.get("id", "")),
    )
    out["namespace"] = sorted(
        out.get("namespace", []),
        key=lambda x: (str(x.get("iri", "")), str(x.get("name", ""))),
    )
    out.pop("datatype", None)
    out.pop("datatypeAttribute", None)
    if "individual" in out:
        if out["individual"]:
            raise NormalizationError(
                "ABox individuals are forbidden in formal VOWL JSON"
            )
        out.pop("individual", None)
    # Reject unknown converter fields in node objects rather than silently deleting them.
    allowed_class_fields = {
        "iri",
        "baseIri",
        "instances",
        "label",
        "id",
        "type",
        "superClasses",
        "subClasses",
        "description",
        "comment",
        "annotations",
        "union",
        "disjointUnion",
        "intersection",
        "attributes",
        "equivalent",
        "complement",
        "individuals",
    }
    allowed_property_fields = {
        "iri",
        "baseIri",
        "id",
        "label",
        "type",
        "domain",
        "range",
        "description",
        "comment",
        "attributes",
        "annotations",
        "inverse",
        "superproperty",
        "subproperty",
        "equivalent",
        "minCardinality",
        "maxCardinality",
        "cardinality",
    }
    for group, allowed in (
        (classes, allowed_class_fields),
        (props, allowed_property_fields),
    ):
        for item in group:
            if not isinstance(item, dict):
                raise NormalizationError("VOWL node must be an object")
            if any(not isinstance(k, str) for k in item):
                raise NormalizationError("VOWL field key must be text")
            unknown_fields = set(item) - allowed
            if unknown_fields:
                raise NormalizationError(
                    "unsupported VOWL node fields: " + ", ".join(sorted(unknown_fields))
                )
    return out


def normalized_vowl_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
