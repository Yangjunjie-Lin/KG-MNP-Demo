from rdflib import OWL, RDF, URIRef

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.semantic_kernel.provenance import compile_statement_provenance
from tests.prompt05_support import candidate


def test_mapping_alignment_cannot_shadow_tbox_reuse_provenance():
    property_iri="urn:example:label"
    reuse=candidate("DATA_PROPERTY",candidate_kind="TBOX",candidate_action="REUSE_EXISTING",target_iri=property_iri)
    mapping=candidate("FIELD_TO_DATA_PROPERTY",candidate_kind="MAPPING",candidate_action="ALIGN_TO_EXISTING",target_iri=property_iri)
    reuse["candidate_id"]="urn:kg-mnp:ontology-candidate:"+"f"*64
    mapping["candidate_id"]="urn:kg-mnp:ontology-candidate:"+"0"*64
    triple=(URIRef(property_iri),RDF.type,OWL.DatatypeProperty)
    _,_,manifest=compile_statement_provenance(candidates={reuse["candidate_id"]:reuse,mapping["candidate_id"]:mapping},item_triples={},item_graph_iris={},
        review_decision_id=stable_urn("ontology-review-decision-log",{"x":1}),review_semantic_hash="1"*64,
        compiler_snapshot_id=stable_urn("semantic-compiler-snapshot",{"x":1}),plan_id=stable_urn("semantic-compilation-plan",{"x":1}),resolved_artifacts={},
        baseline_statement_sources={triple:({"graph_role":"effective-tbox","asset_path":"baseline/ontology.nt","lock_path":"baseline/pack.lock.json","pack_lock_id":stable_urn("domain-pack-lock",{"x":1})},)},
        baseline_graph_iris={"effective-tbox":"urn:example:tbox","effective-shapes":"urn:example:shapes"})
    assert manifest["statements"][0]["confirmed_item_id"]==reuse["candidate_id"]
