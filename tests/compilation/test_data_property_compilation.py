import pytest
from rdflib import Graph, Literal, URIRef, XSD

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


@pytest.mark.parametrize(
    "lexical",
    ["bad", "2026-13-01", "2026-02-30", "2026-08-06T12:00:00Z"],
)
def test_invalid_xsd_date_lexical_rejected(lexical):
    with pytest.raises(ABoxCompilationError, match="xsd:date"):
        _literal({"value": lexical, "datatype_iri": str(XSD.date)})


@pytest.mark.parametrize(
    "lexical",
    [
        "bad",
        "2026-13-01T00:00:00Z",
        "2026-02-30T00:00:00Z",
        "2026-08-06",
        "2026-08-06T12:00:00",
        "2026-08-06 12:00:00Z",
    ],
)
def test_invalid_xsd_datetime_lexical_rejected(lexical):
    with pytest.raises(ABoxCompilationError, match="xsd:dateTime"):
        _literal({"value": lexical, "datatype_iri": str(XSD.dateTime)})


@pytest.mark.parametrize(
    ("lexical", "datatype"),
    [
        ("2026-08-06T12:00:00Z", XSD.date),
        ("2026-08-06", XSD.dateTime),
    ],
)
def test_date_datetime_cross_type_rejected(lexical, datatype):
    with pytest.raises(ABoxCompilationError):
        _literal({"value": lexical, "datatype_iri": str(datatype)})


@pytest.mark.parametrize(
    ("lexical", "datatype"),
    [
        ("2026-08-06", XSD.date),
        ("2026-08-06T12:00:00Z", XSD.dateTime),
        ("2026-08-06T12:00:00.123Z", XSD.dateTime),
    ],
)
def test_supported_date_lexicals_round_trip(lexical, datatype):
    literal = _literal({"value": lexical, "datatype_iri": str(datatype)})
    assert str(literal) == lexical
    assert literal.datatype == datatype

    subject = URIRef("urn:kg-mnp:test:subject")
    predicate = URIRef("urn:kg-mnp:test:predicate")
    graph = Graph()
    graph.add((subject, predicate, literal))
    serialized = graph.serialize(format="nt")
    assert lexical in serialized
    parsed = Graph()
    parsed.parse(data=serialized, format="nt")
    round_tripped = next(parsed.objects(subject, predicate))
    assert isinstance(round_tripped, Literal)
    assert round_tripped.toPython() == literal.toPython()
    assert round_tripped.datatype == datatype
