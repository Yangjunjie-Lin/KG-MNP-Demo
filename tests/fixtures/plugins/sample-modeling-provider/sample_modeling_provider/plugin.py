"""Deterministic external provider used only for SDK conformance."""

from kg_mnp.modeling.control_plane.providers.models import (
    candidate_body,
    candidate_draft,
)


class SampleModelingProvider:
    def propose(self, request):
        return (
            candidate_draft(
                draft_ref="external-class",
                draft_kind="TBOX",
                candidate_action="CREATE_NEW",
                body=candidate_body(
                    candidate_type="CLASS",
                    target_iri="urn:kg-mnp:fixture:external-class",
                    label="External Fixture Class",
                ),
                rationale="independent fixture domain-modeling evidence",
                domain_asset_refs=["sample-modeling-provider-fixture"],
            ),
        )
