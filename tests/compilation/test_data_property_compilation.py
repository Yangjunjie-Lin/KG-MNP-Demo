import pytest
from rdflib import Literal, XSD

from kg_mnp_demo.compilation.abox_compiler import ABoxCompilationError, _literal, compile_abox
from ._helpers import authorities


def test_data_property_is_a_typed_literal():
    values = authorities()
    _, assertions = compile_abox(values[3], values[1], values[4])
    data = next(item for item in assertions if item.candidate_kind == "DATA_PROPERTY_ASSERTION")
    assert isinstance(data.triple[2], Literal)
    assert str(data.triple[2].datatype).endswith("#string")


@pytest.mark.parametrize("value", [
    {"value": None, "datatype_iri": str(XSD.string)},
    {"value": "not-an-integer", "datatype_iri": str(XSD.integer)},
    {"value": "x", "datatype_iri": "urn:unsupported:datatype"},
])
def test_null_or_invalid_typed_literal_is_rejected(value):
    with pytest.raises(ABoxCompilationError):
        _literal(value)
