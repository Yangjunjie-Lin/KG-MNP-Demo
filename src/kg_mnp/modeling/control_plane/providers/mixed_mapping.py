"""Explicit cross-source identities and bounded text extraction, proposal-only.

Templates are literal delimiters with named slots, not user regex or NLP.
Every fact is bound to a verified KG-IR cell or exact text span. Identical
canonical facts merge in the existing normalizer; contradictions remain there
for review. No ontology/registry writes and no external calls occur here.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from pydantic import ValidationError

from kg_mnp.contracts.canonical import semantic_hash

from ..errors import ModelingControlError
from ..limits import ModelingLimits
from ..mappings import table_identity
from .models import candidate_body, candidate_draft
from .record_profile import MixedRecordMapping

XSD = "http://www.w3.org/2001/XMLSchema#"


def fail(code, message):
    raise ModelingControlError(f"{code}: {message}")


def typed_value(value, datatype):
    if value is None:
        return None
    lexical = value if datatype == "string" else value.strip()
    try:
        if datatype == "integer":
            if not re.fullmatch(r"[+-]?[0-9]+", lexical):
                raise ValueError()
            lexical = str(int(lexical))
        elif datatype == "decimal":
            if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", lexical):
                raise ValueError()
            number = Decimal(lexical)
            lexical = format(number, "f")
            if "." in lexical:
                lexical = lexical.rstrip("0").rstrip(".")
            if number == 0:
                lexical = "0"
        elif datatype == "boolean":
            lexical = {"true": "true", "false": "false", "1": "true", "0": "false"}[lexical]
        elif datatype == "date":
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", lexical):
                raise ValueError()
            date.fromisoformat(lexical)
        elif datatype == "dateTime":
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})?", lexical):
                raise ValueError()
            datetime.fromisoformat(lexical)
        elif datatype != "string":
            raise ValueError()
    except (ValueError, KeyError, InvalidOperation) as exc:
        raise ModelingControlError("MAPPING_DATATYPE_INVALID: value is not valid for declared datatype") from exc
    return {"lexical_value": lexical, "datatype_iri": XSD + datatype, "language": None}


def template_slots(template):
    parts = re.split(r"\{([A-Za-z][A-Za-z0-9_]*)\}", template)
    names = parts[1::2]
    if (not names or len(names) > 20 or len(set(names)) != len(names)
            or any("{" in p or "}" in p for p in parts[::2])
            or any(not p for p in parts[2:-1:2])):
        fail("TEXT_TEMPLATE_INVALID", "use unique named slots separated by literal text")
    return parts


def match_template(parts, text):
    """Linear delimiter matching; repeated delimiters are rejected as ambiguous."""
    if not text.startswith(parts[0]) or not text.endswith(parts[-1]):
        return None
    offset, spans = len(parts[0]), []
    for index in range(1, len(parts), 2):
        delimiter = parts[index + 1]
        final = index == len(parts) - 2
        end = len(text) - len(delimiter) if final else text.find(delimiter, offset)
        if end <= offset:
            return None
        if delimiter and text.find(delimiter, offset, end) != -1:
            fail("TEXT_TEMPLATE_AMBIGUOUS", "delimiter appears inside a captured value; annotate exact spans")
        spans.append({"field": parts[index], "start": offset, "end": end, "quote": text[offset:end]})
        offset = end + len(delimiter)
    if offset != len(text):
        return None
    if any(delimiter in span["quote"] for delimiter in parts[2::2] if delimiter for span in spans):
        fail("TEXT_TEMPLATE_AMBIGUOUS", "literal delimiters inside values require exact manual spans")
    return spans


def input_inventory(datasets):
    evidence = {e["evidence_id"]: e for d in datasets for e in d["evidence_records"]}
    tables, text_items, data_ids = {}, [], []
    for dataset in datasets:
        for item in dataset["items"]:
            kind = item["item_kind"]
            if kind == "table-cell":
                identity = table_identity(item, evidence)
                table = tables.setdefault(identity, {"source_id": identity[0], "locator": {
                    "locator_kind": identity[1], "sheet": identity[2] if identity[1] == "spreadsheet-cell" else None,
                    "table_index": identity[2] if identity[1] == "document-table-cell" else None}, "headers": [], "item_ids": []})
                table["item_ids"].append(item["item_id"])
                if item["payload"]["row"] == 1:
                    table["headers"].append({"column": item["payload"]["column"], "name": item["payload"]["value"]["normalized_lexical_value"]})
                else:
                    data_ids.append(item["item_id"])
            elif kind == "text-block" and item["payload"]["text"].strip():
                text_items.append({"item_id": item["item_id"], "source_ids": item["source_ids"],
                                   "text": item["payload"]["text"], "evidence_refs": item["evidence_refs"]})
                data_ids.append(item["item_id"])
            elif kind == "scalar-field":
                data_ids.append(item["item_id"])
    return {"tables": list(tables.values()), "text_items": text_items, "data_item_ids": sorted(data_ids)}


def mixed_mapping_drafts(*, rules, datasets, namespace, baseline, question_ids, asset_id=None):
    try:
        rules = MixedRecordMapping.model_validate(rules).model_dump()
    except ValidationError as exc:
        raise ModelingControlError("MAPPING_PROFILE_INVALID: invalid closed v2 profile") from exc
    digest = semantic_hash(rules)
    elements = {e["iri"]: e for e in baseline["elements"]}
    items = {i["item_id"]: i for d in datasets for i in d["items"]}
    evidence = {e["evidence_id"]: e for d in datasets for e in d["evidence_records"]}
    inventory = input_inventory(datasets)
    tables = {}
    for item in items.values():
        if item["item_kind"] == "table-cell":
            identity = table_identity(item, evidence)
            coordinate = (item["payload"]["row"], item["payload"]["column"])
            cells = tables.setdefault(identity, {})
            if coordinate in cells and cells[coordinate] != item:
                fail("MAPPING_TABLE_AMBIGUOUS", "conflicting cells at the same coordinate")
            cells[coordinate] = item
    occurrences, spans, consumed, record_ids, spaces, aliases = [], [], set(), set(), {}, {}

    def element(iri, kind):
        value = elements.get(iri)
        if not value or value["element_kind"] != kind:
            fail("MAPPING_BASELINE_INVALID", "mapping targets must be a locked baseline element of the declared kind")
        return value["element_id"]

    definitions = [*rules["tables"], *rules["text_templates"], *rules["text_records"]]
    for definition in definitions:
        key, space = definition["record_id"], definition["identity_space"]
        if key in record_ids:
            fail("MAPPING_IDENTITY_CONFLICT", "record definition IDs must be unique")
        record_ids.add(key)
        element(definition["class_iri"], "CLASS")
        if space in spaces and spaces[space] != definition["class_iri"]:
            fail("MAPPING_IDENTITY_CONFLICT", "one identity space cannot imply different classes")
        spaces[space] = definition["class_iri"]
        for alias in definition["identity_aliases"]:
            slot = (space, alias["value"])
            if slot in aliases and aliases[slot] != alias["canonical"]:
                fail("MAPPING_ALIAS_CONFLICT", "identity alias has multiple canonical targets")
            aliases[slot] = alias["canonical"]
        for mapping in definition["literals"].values():
            element(mapping["predicate_iri"], "DATA_PROPERTY")
        for link in definition["references"]:
            element(link["predicate_iri"], "OBJECT_PROPERTY")
    if any((space, target) in aliases and aliases[space, target] != target for (space, _), target in aliases.items()):
        fail("MAPPING_ALIAS_CONFLICT", "aliases must point directly to canonical keys, not chains or cycles")

    def identity(space, value):
        value = aliases.get((space, value), value)
        if not isinstance(value, str) or not value or value != value.strip() or len(value) > 200 or any(ord(c) < 32 for c in value):
            fail("MAPPING_IDENTIFIER_REQUIRED", "explicit nonempty business identity required")
        return namespace + space + ":" + quote(value, safe="")

    def add_record(definition, fields, origin):
        required = {definition["id_field"], *definition["literals"], *(r["field"] for r in definition["references"])}
        if not required <= fields.keys():
            fail("MAPPING_FIELD_MISSING", "a declared identity, literal or reference field is absent")
        # Unmapped fields are deliberately not claimed as consumed.
        selected = {key: fields[key] for key in required}
        iri = identity(definition["identity_space"], fields[definition["id_field"]][0])
        occurrences.append({"definition": definition, "fields": selected, "iri": iri,
                            "ref": "record-" + semantic_hash([definition["record_id"], origin])})
        consumed.update(cell[1]["item_id"] for cell in selected.values())
        if len(occurrences) > ModelingLimits().max_total_candidates:
            fail("MAPPING_LIMIT_EXCEEDED", "record expansion exceeds proposal limit")

    for definition in rules["tables"]:
        locator = definition["locator"]
        kind = locator["locator_kind"]
        selector = locator["sheet"] if kind == "spreadsheet-cell" else locator["table_index"]
        if ((kind != "spreadsheet-cell" and locator["sheet"] is not None)
                or (kind != "document-table-cell" and locator["table_index"] is not None)):
            fail("MAPPING_TABLE_INVALID", "irrelevant table selector is forbidden")
        cells = tables.get((definition["source_id"], kind, selector))
        if not cells:
            fail("MAPPING_TABLE_MISSING", "selected Source/table is not in the verified dataset")
        headers = {column: item["payload"]["value"]["normalized_lexical_value"] for (row, column), item in cells.items() if row == 1}
        if not headers or None in headers.values() or "" in headers.values() or len(set(headers.values())) != len(headers):
            fail("MAPPING_HEADER_INVALID", "table needs unique nonempty first-row headers")
        rows = {}
        for (row, column), item in cells.items():
            if row > 1 and column in headers:
                rows.setdefault(row, {})[headers[column]] = (item["payload"]["value"]["normalized_lexical_value"], item)
        for row, fields in sorted(rows.items()):
            add_record(definition, fields, [definition["source_id"], locator, row])

    def bind_spans(definition, values, origin):
        fields = {}
        for span in values:
            item = items.get(span["item_id"])
            if not item or item["item_kind"] != "text-block" or not item["evidence_refs"]:
                fail("MAPPING_EVIDENCE_INVALID", "text annotation must reference a verified text item")
            text = item["payload"]["text"]
            if not (0 <= span["start"] < span["end"] <= len(text)) or text[span["start"]:span["end"]] != span["quote"]:
                fail("MAPPING_EVIDENCE_INVALID", "text quote must match exact Unicode character offsets")
            if span["field"] in fields:
                fail("MAPPING_FIELD_AMBIGUOUS", "a record field cannot have multiple spans")
            fields[span["field"]] = (span["quote"], item)
            spans.append({**span, "record_id": definition["record_id"], "evidence_refs": item["evidence_refs"]})
        add_record(definition, fields, origin)

    for definition in rules["text_templates"]:
        parts = template_slots(definition["template"])
        count = 0
        for item in inventory["text_items"]:
            if definition["source_id"] not in item["source_ids"]:
                continue
            values = match_template(parts, item["text"])
            if values:
                bind_spans(definition, [{**s, "item_id": item["item_id"]} for s in values], item["item_id"])
                count += 1
        if not count:
            fail("TEXT_TEMPLATE_NO_MATCH", "template matched no complete text block in its selected Source")
    for definition in rules["text_records"]:
        bind_spans(definition, definition["fields"], definition["record_id"])
    if not occurrences:
        fail("MAPPING_EMPTY", "profile must produce at least one evidence-bound record")

    exclusions = {e["item_id"] for e in rules["exclusions"]}
    if len(exclusions) != len(rules["exclusions"]) or not exclusions <= set(inventory["data_item_ids"]) or exclusions & consumed:
        fail("MAPPING_EXCLUSION_INVALID", "exclusions must be unique unconsumed data items in this dataset")
    identities = {}
    for occurrence in occurrences:
        identities.setdefault(occurrence["iri"], []).append(occurrence)
    drafts = []

    def draft(occurrence, suffix, kind, body, bindings, dependencies=(), baseline_refs=()):
        drafts.append(candidate_draft(draft_ref=occurrence["ref"] + suffix, draft_kind=kind,
            candidate_action="ALIGN_TO_EXISTING" if kind == "MAPPING" else "ASSERT", body=body,
            rationale=f"Explicit mixed-source mapping; human review required; mapping-sha256:{digest}",
            kg_ir_item_refs=[cell[1]["item_id"] for cell in bindings],
            evidence_refs=[e for cell in bindings for e in cell[1]["evidence_refs"]],
            domain_asset_refs=[asset_id] if asset_id else [], competency_question_refs=question_ids,
            baseline_element_refs=baseline_refs, dependency_draft_refs=dependencies))
        if len(drafts) > ModelingLimits().max_total_candidates:
            fail("MAPPING_LIMIT_EXCEEDED", "expanded candidates exceed proposal limit")

    for occurrence in occurrences:
        definition, fields, iri, ref = (occurrence[k] for k in ("definition", "fields", "iri", "ref"))
        bindings = list(fields.values())
        draft(occurrence, "", "ABOX", candidate_body(candidate_type="INDIVIDUAL", subject_iri=iri), bindings)
        draft(occurrence, "-class", "ABOX", candidate_body(candidate_type="CLASS_ASSERTION", subject_iri=iri, object_iri=definition["class_iri"]),
              bindings, [ref], [element(definition["class_iri"], "CLASS")])
        for index, (field, mapping) in enumerate(sorted(definition["literals"].items())):
            suffix = str(index)
            literal = typed_value(fields[field][0], mapping["datatype"])
            property_id = element(mapping["predicate_iri"], "DATA_PROPERTY")
            draft(occurrence, "-mapping-" + suffix, "MAPPING", candidate_body(candidate_type="FIELD_TO_DATA_PROPERTY",
                source_field=field, target_iri=mapping["predicate_iri"], conversion_policy="IDENTITY" if mapping["datatype"] == "string" else "CONTROLLED_LOOKUP", null_policy="OMIT"), [fields[field]], baseline_refs=[property_id])
            if literal is not None:
                draft(occurrence, "-value-" + suffix, "ABOX", candidate_body(candidate_type="DATA_PROPERTY_ASSERTION", subject_iri=iri,
                    predicate_iri=mapping["predicate_iri"], literal=literal), [fields[field], fields[definition["id_field"]]], [ref, ref + "-mapping-" + suffix], [property_id])
        for index, link in enumerate(definition["references"]):
            target_iri = identity(link["target_space"], fields[link["field"]][0])
            targets = identities.get(target_iri)
            if not targets:
                fail("MAPPING_REFERENCE_INVALID", "referenced canonical identity is absent from mapped records")
            draft(occurrence, f"-link-{index}", "ABOX", candidate_body(candidate_type="OBJECT_PROPERTY_ASSERTION", subject_iri=iri,
                predicate_iri=link["predicate_iri"], object_iri=target_iri), [fields[link["field"]], fields[definition["id_field"]]],
                [ref, targets[0]["ref"]], [element(link["predicate_iri"], "OBJECT_PROPERTY")])
    report = {"mapping_digest": digest, "mapped_item_ids": sorted(consumed), "exclusions": rules["exclusions"],
              "unmapped_item_ids": sorted(set(inventory["data_item_ids"]) - consumed - exclusions), "text_spans": spans,
              "identities": [{"iri": iri, "occurrences": len(records),
                              "item_ids": sorted({cell[1]["item_id"] for r in records for cell in r["fields"].values()})}
                             for iri, records in sorted(identities.items())]}
    return drafts, report
