import pytest
from rdflib import Graph
from rdflib.compare import isomorphic

from kg_mnp_demo.graphdb.repository_config import RepositoryConfigError, repository_config_document, repository_config_semantic_hash, render_repository_config_nt, render_repository_config_ttl


def test_repository_config_is_deterministic_and_empty_ruleset():
    document = repository_config_document("kg-mnp-0123456789abcdef0123")
    ttl = render_repository_config_ttl(document)
    assert ttl == render_repository_config_ttl(document)
    assert b'graphdb:ruleset "empty"' in ttl
    assert b'graphdb:disable-sameAs "true"' in ttl
    nt = render_repository_config_nt(document)
    assert nt.endswith(b"\n")
    ttl_graph = Graph().parse(data=ttl.decode("utf-8"), format="turtle")
    nt_graph = Graph().parse(data=nt.decode("utf-8"), format="nt")
    assert isomorphic(ttl_graph, nt_graph)
    other = repository_config_document("kg-mnp-fedcba9876543210fedc")
    assert repository_config_semantic_hash(document) == repository_config_semantic_hash(other)


def test_repository_config_rejects_inference():
    document = repository_config_document("kg-mnp-0123456789abcdef0123")
    document["ruleset"] = "rdfs"
    with pytest.raises(RepositoryConfigError):
        render_repository_config_ttl(document)
