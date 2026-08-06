from rdflib import RDF

from kg_mnp_demo.compilation.abox_compiler import compile_abox
from ._helpers import authorities


def test_entity_compiles_only_type_assertion():
    values = authorities()
    graph, assertions = compile_abox(values[3], values[1], values[4])
    entity = next(item for item in assertions if item.candidate_kind == "ENTITY")
    assert (entity.triple[0], RDF.type, entity.triple[2]) in graph
