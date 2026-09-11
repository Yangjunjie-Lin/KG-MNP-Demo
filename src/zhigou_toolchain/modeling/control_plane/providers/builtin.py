"""Four offline built-in modeling providers."""

from __future__ import annotations

from zhigou_toolchain.contracts.canonical import semantic_hash

from ..mappings import table_identity
from .models import ImmutableModelingProviderRequest, candidate_body, candidate_draft


class ManualCandidateProvider:
    def propose(self, request: ImmutableModelingProviderRequest) -> tuple[dict, ...]:
        drafts = request.context.get("manual_drafts", [])
        return tuple(drafts)


class BaselineReuseProvider:
    def propose(self, request: ImmutableModelingProviderRequest) -> tuple[dict, ...]:
        context = request.context
        elements = {item["element_id"]: item for item in context.get("baseline_elements", [])}
        drafts = []
        for index, alignment in enumerate(context.get("alignments", [])):
            if not alignment.get("target_element_id"):
                continue
            element = elements.get(alignment["target_element_id"])
            if element is None:
                continue
            kind = "TBOX"
            candidate_type = element["element_kind"] if element["element_kind"] in {"CLASS", "OBJECT_PROPERTY", "DATA_PROPERTY"} else "CLASS"
            drafts.append(candidate_draft(
                draft_ref=f"reuse-{index:08d}", draft_kind=kind, candidate_action="REUSE_EXISTING",
                body=candidate_body(candidate_type=candidate_type, target_iri=element["iri"], label=element["labels"][0]["value"] if element["labels"] else None),
                baseline_element_refs=[element["element_id"]],
                rationale="reuse a locked baseline element suggested by reviewed lexical alignment",
                evidence_refs=alignment.get("evidence_refs", []),
                domain_asset_refs=[element["source_asset_id"]],
                score_basis=alignment["score_basis"], score_basis_points=alignment["score_basis_points"],
            ))
        return tuple(drafts)


class RuleMappingProvider:
    def propose(self, request: ImmutableModelingProviderRequest) -> tuple[dict, ...]:
        context = request.context
        items = {item["item_id"]: item for item in context.get("kg_ir_items", [])}
        elements_by_iri = {
            item["iri"]: item for item in context.get("baseline_elements", [])
        }
        class_elements = sorted(
            (
                item
                for item in elements_by_iri.values()
                if item["element_kind"] == "CLASS"
            ),
            key=lambda item: item["iri"],
        )
        # Multiple classes require an explicit mapping; alphabetical order has
        # no domain meaning and must never decide an individual's type.
        default_class = class_elements[0] if len(class_elements) == 1 else None
        evidence = {e["evidence_id"]: e for e in context.get("evidence_records", [])}
        default_namespace = context.get("default_namespace", "urn:kg-mnp:proposed:")
        question_refs = context.get("competency_question_ids", [])
        drafts = []
        individual_refs: dict[str, str] = {}
        for index, mapping in enumerate(context.get("field_mappings", [])):
            source = items.get(mapping["source_item_id"])
            if source is None or not mapping["target_property_iri"]:
                continue
            parent_ref = source.get("parent_item_id") or source["item_id"]
            if source["item_kind"] == "table-cell":
                parent_ref = semantic_hash({"table": table_identity(source, evidence), "row": source["payload"]["row"]})
            else:
                # JSON leaves share a document root in KG-IR, not a business
                # record. Only the evidence pointer gives their actual parent.
                locations = [evidence[e]["locator"] for e in source["evidence_refs"] if e in evidence]
                pointers = {loc["pointer"].rpartition("/")[0] for loc in locations if loc["locator_kind"] == "json-pointer"}
                parent_ref = semantic_hash({"sources": sorted(source["source_ids"]),
                    "json_parent": next(iter(pointers)) if len(pointers) == 1 and len(locations) == len(source["evidence_refs"]) else None,
                    "item": None if len(pointers) == 1 and len(locations) == len(source["evidence_refs"]) else source["item_id"]})
            subject_iri = f"{default_namespace}entity-{parent_ref}"
            individual_ref = individual_refs.get(parent_ref)
            if individual_ref is None:
                individual_ref = f"individual-{len(individual_refs):08d}"
                individual_refs[parent_ref] = individual_ref
                drafts.append(
                    candidate_draft(
                        draft_ref=individual_ref,
                        draft_kind="ABOX",
                        candidate_action="ASSERT",
                        body=candidate_body(
                            candidate_type="INDIVIDUAL", subject_iri=subject_iri
                        ),
                        kg_ir_item_refs=[source["item_id"]],
                        evidence_refs=source["evidence_refs"],
                        competency_question_refs=question_refs,
                        rationale="deterministic evidence-bound individual IRI proposal",
                    )
                )
                if default_class is not None:
                    drafts.append(
                        candidate_draft(
                            draft_ref=f"class-assertion-{len(individual_refs) - 1:08d}",
                            draft_kind="ABOX",
                            candidate_action="ASSERT",
                            body=candidate_body(
                                candidate_type="CLASS_ASSERTION",
                                subject_iri=subject_iri,
                                object_iri=default_class["iri"],
                            ),
                            kg_ir_item_refs=[source["item_id"]],
                            evidence_refs=source["evidence_refs"],
                            competency_question_refs=question_refs,
                            baseline_element_refs=[default_class["element_id"]],
                            dependency_draft_refs=[individual_ref],
                            rationale="baseline class assertion proposal for an evidence-bound individual",
                        )
                    )
            mapping_ref = f"mapping-{index:08d}"
            property_element = elements_by_iri.get(mapping["target_property_iri"])
            drafts.append(candidate_draft(
                draft_ref=mapping_ref, draft_kind="MAPPING", candidate_action="ALIGN_TO_EXISTING",
                body=candidate_body(candidate_type="FIELD_TO_DATA_PROPERTY", source_field=mapping["source_field_name"], target_iri=mapping["target_property_iri"], conversion_policy=mapping["conversion_policy"], null_policy=mapping["null_policy"]),
                kg_ir_item_refs=[source["item_id"]], evidence_refs=source["evidence_refs"],
                competency_question_refs=question_refs,
                baseline_element_refs=[property_element["element_id"]] if property_element else [],
                rationale="controlled KG-IR field-to-property mapping candidate",
            ))
            value = source["payload"]["value"]
            if mapping["target_property_iri"] and value["null_state"] == "NOT_NULL":
                drafts.append(candidate_draft(
                    draft_ref=f"abox-{index:08d}", draft_kind="ABOX", candidate_action="ASSERT",
                    body=candidate_body(candidate_type="DATA_PROPERTY_ASSERTION", subject_iri=subject_iri, predicate_iri=mapping["target_property_iri"], literal={"lexical_value": value["normalized_lexical_value"], "datatype_iri": "http://www.w3.org/2001/XMLSchema#" + value["datatype"] if value["datatype"] in {"integer", "decimal", "boolean"} else None, "language": None}),
                    kg_ir_item_refs=[source["item_id"]], evidence_refs=source["evidence_refs"],
                    competency_question_refs=question_refs,
                    baseline_element_refs=[property_element["element_id"]] if property_element else [],
                    dependency_draft_refs=[individual_ref, mapping_ref],
                    rationale="evidence-bound ABox assertion draft with a deterministic proposed subject IRI",
                ))
        return tuple(drafts)


class RecordedModelOutputProvider:
    def propose(self, request: ImmutableModelingProviderRequest) -> tuple[dict, ...]:
        return tuple(request.context.get("recorded_candidate_drafts", []))
