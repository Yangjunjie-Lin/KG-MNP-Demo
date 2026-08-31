"""Four offline built-in modeling providers."""

from __future__ import annotations

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
        default_class = class_elements[0] if class_elements else None
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
                parent_ref = f"{parent_ref}:row:{source['payload']['row']}"
            individual_ref = individual_refs.get(parent_ref)
            if individual_ref is None:
                individual_ref = f"individual-{len(individual_refs):08d}"
                individual_refs[parent_ref] = individual_ref
                subject_iri = f"{default_namespace}entity-{parent_ref.rsplit(':', 1)[-1]}"
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
                    body=candidate_body(candidate_type="DATA_PROPERTY_ASSERTION", subject_iri=f"{default_namespace}entity-{parent_ref.rsplit(':', 1)[-1]}", predicate_iri=mapping["target_property_iri"], literal={"lexical_value": value["normalized_lexical_value"], "datatype_iri": None, "language": None}),
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
