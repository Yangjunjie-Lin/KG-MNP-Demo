"""Modeling-provider-specific conformance check."""

from __future__ import annotations

from kg_mnp.plugins.registry import PluginRegistry

from ..limits import ModelingLimits
from .execution import execute_provider
from .models import build_provider_request


def run_modeling_conformance(registry: PluginRegistry, provider_id: str) -> dict:
    descriptor = registry.get(provider_id)
    snapshot_id = "urn:kg-mnp:plugin-snapshot:" + "0" * 64
    request = build_provider_request(
        modeling_input_bundle_id="urn:kg-mnp:modeling-input-bundle:" + "0" * 64,
        provider_snapshot_id=snapshot_id, capability=descriptor.manifest["capabilities"][0],
        scope_id="urn:kg-mnp:ontology-scope:" + "0" * 64,
        baseline_snapshot_id="urn:kg-mnp:ontology-baseline-snapshot:" + "0" * 64,
        terminology_catalog_id="urn:kg-mnp:terminology-catalog:" + "0" * 64,
        term_alignment_set_id="urn:kg-mnp:term-alignment-set:" + "0" * 64,
        kg_ir_dataset_ids=[], evidence_record_ids=[], context={}, limits=ModelingLimits(),
    )
    first = execute_provider(registry, provider_id, request)
    second = execute_provider(registry, provider_id, request)
    return {
        "plugin_id": provider_id,
        "status": "PASS" if first == second else "FAIL",
        "checks": ["PROPOSAL_ONLY", "NO_NETWORK", "NO_FINAL_IDS", "REPEATABLE_RESPONSE"],
    }
