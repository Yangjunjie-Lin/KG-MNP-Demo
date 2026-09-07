from kg_mnp.lifecycle.diff.engine import create_diff


def test_same_ontology_version_identity_is_explicit_metadata_not_unknown_semantics():
    base={"package_id":"urn:kg-mnp:ontology-package:"+"1"*64,"ontology_iri":"urn:example:ontology","version":"0.1.0"}
    candidate={**base,"package_id":"urn:kg-mnp:ontology-package:"+"2"*64,"version":"0.1.1"}
    diff=create_diff(base,candidate,base_version="0.1.0",candidate_version="0.1.1")
    assert diff["identity_changes"]
    assert diff["overall_classification"]=="PATCH_COMPATIBLE"


def test_changed_ontology_identity_remains_blocking():
    base={"package_id":"urn:kg-mnp:ontology-package:"+"1"*64,"ontology_iri":"urn:example:ontology"}
    candidate={**base,"ontology_iri":"urn:different:ontology"}
    assert create_diff(base,candidate)["overall_classification"]=="UNKNOWN_REQUIRES_REVIEW"
