import json
from types import SimpleNamespace

import pytest
from rdflib import Dataset

from kg_mnp_demo.graphdb.verifier import (
    GraphDBVerificationError,
    expected_review_audit_rows,
    semantic_hash_nquads,
    verify_imported_repository,
)

from ._helpers import ROOT


def test_export_hash_is_order_independent_and_detects_content_change():
    first = b"<urn:s> <urn:p> <urn:o> <urn:g> .\n<urn:s2> <urn:p> \"v\" <urn:g> .\n"
    reordered = b"<urn:s2> <urn:p> \"v\" <urn:g> .\n<urn:s> <urn:p> <urn:o> <urn:g> .\n"
    changed = b"<urn:s> <urn:p> <urn:other> <urn:g> .\n<urn:s2> <urn:p> \"v\" <urn:g> .\n"
    assert semantic_hash_nquads(first) == semantic_hash_nquads(reordered)
    assert semantic_hash_nquads(first) != semantic_hash_nquads(changed)


def test_rdf11_plain_and_explicit_xsd_string_have_same_semantic_hash():
    plain = b'<urn:s> <urn:p> "ACTIVE" <urn:g> .\n'
    typed = (
        b'<urn:s> <urn:p> "ACTIVE"^^'
        b'<http://www.w3.org/2001/XMLSchema#string> <urn:g> .\n'
    )

    assert semantic_hash_nquads(plain) == semantic_hash_nquads(typed)


def test_export_blank_nodes_are_rejected():
    with pytest.raises(GraphDBVerificationError):
        semantic_hash_nquads(b"_:b <urn:p> <urn:o> <urn:g> .\n")


def test_verifier_rejects_complete_export_with_inferred_statement():
    package = ROOT / "examples" / "graphdb" / "expected" / "full-confirmation"
    explicit = (package / "import" / "knowledge-graph.nq").read_bytes()
    complete = explicit + b"<urn:inferred:s> <urn:inferred:p> <urn:inferred:o> <urn:inferred:g> .\n"
    dataset = Dataset()
    dataset.parse(data=explicit.decode("utf-8"), format="nquads")
    suite = json.loads(
        (package / "verification" / "query-suite-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    review_rows = expected_review_audit_rows(suite["expected"]["review_audit"])

    def raw_review_result():
        variables = [
            "log",
            "session",
            "reviewer",
            "decision",
            "outcome",
            "decidedAt",
            "subject",
        ]
        bindings = []
        for row in review_rows:
            binding = {}
            for variable in variables:
                term = dict(row[variable])
                if "language" in term:
                    term["xml:lang"] = term.pop("language")
                binding[variable] = term
            bindings.append(binding)
        return {"head": {"vars": variables}, "results": {"bindings": bindings}}

    class Client:
        def count_repository_statements(self, repository_id):
            return len(list(dataset.quads((None, None, None, None))))

        def assert_default_graph_empty(self, repository_id):
            return SimpleNamespace(
                http_status=200,
                statement_count=0,
                semantic_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                content_type="application/n-triples",
            )

        def sparql_select(self, repository_id, query):
            if "SELECT ?log ?session ?reviewer ?decision" in query:
                return raw_review_result()
            if "FILTER(false)" in query:
                return {
                    "head": {"vars": ["s", "p", "o"]},
                    "results": {"bindings": []},
                }
            return json.loads(dataset.query(query).serialize(format="json"))

        def sparql_ask(self, repository_id, query):
            return bool(dataset.query(query).askAnswer)

        def export_nquads(self, repository_id, *, include_inferred=False):
            return complete if include_inferred else explicit

    with pytest.raises(
        GraphDBVerificationError,
        match="full export contains inferred statements",
    ):
        verify_imported_repository(Client(), package)
