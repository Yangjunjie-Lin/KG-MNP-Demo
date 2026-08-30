from kg_mnp.compilation.abox_compiler import compile_abox

from ._helpers import authorities


def test_full_package_compiles_class_and_assertion_kinds_without_inference():
    values = authorities()
    graph, assertions = compile_abox(values[3], values[1], values[4])
    assert len(assertions) == 5
    assert len(graph) >= len(assertions)
