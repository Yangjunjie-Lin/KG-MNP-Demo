import pytest

from kg_mnp_demo.graphdb.verifier import GraphDBVerificationError, semantic_hash_nquads


def test_export_hash_is_order_independent_and_detects_content_change():
    first = b"<urn:s> <urn:p> <urn:o> <urn:g> .\n<urn:s2> <urn:p> \"v\" <urn:g> .\n"
    reordered = b"<urn:s2> <urn:p> \"v\" <urn:g> .\n<urn:s> <urn:p> <urn:o> <urn:g> .\n"
    changed = b"<urn:s> <urn:p> <urn:other> <urn:g> .\n<urn:s2> <urn:p> \"v\" <urn:g> .\n"
    assert semantic_hash_nquads(first) == semantic_hash_nquads(reordered)
    assert semantic_hash_nquads(first) != semantic_hash_nquads(changed)


def test_export_blank_nodes_are_rejected():
    with pytest.raises(GraphDBVerificationError):
        semantic_hash_nquads(b"_:b <urn:p> <urn:o> <urn:g> .\n")
