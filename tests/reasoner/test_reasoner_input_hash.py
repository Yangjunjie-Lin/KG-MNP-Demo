from __future__ import annotations

from pathlib import Path

from rdflib import Graph

import run_reasoner as reasoner


def test_canonicalization_dependency_is_exactly_pinned():
    assert reasoner.EXPECTED_RDFLIB_VERSION == "7.6.0"
    assert reasoner.installed_rdflib_version() == reasoner.EXPECTED_RDFLIB_VERSION
    pyproject = (reasoner.ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"rdflib==7.6.0"' in pyproject


def _write_minimal_release(root: Path, *, newline: str = "\n") -> None:
    (root / "config").mkdir(parents=True)
    (root / "ontology").mkdir()
    config = """ontology_version: "1.0.0"
modules:
  - code: CORE
    file: core.ttl
    runtime: true
    optional: false
  - code: ALIGNMENTS
    file: alignments.ttl
    runtime: false
    optional: true
root:
  file: root.ttl
  ontology_iri: "https://example.test/root"
  catalog: catalog.xml
""".replace("\n", newline)
    (root / "config" / "ontology_modules.yaml").write_text(
        config,
        encoding="utf-8",
        newline="",
    )
    for name, content in {
        "root.ttl": "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n<https://example.test/root> a owl:Ontology .\n",
        "core.ttl": "<https://example.test/A> <https://example.test/p> <https://example.test/B> .\n",
        "alignments.ttl": "<https://example.test/A> <https://example.test/aligned> <https://external.test/A> .\n",
        "catalog.xml": "<catalog/>\n",
    }.items():
        (root / "ontology" / name).write_text(
            content.replace("\n", newline),
            encoding="utf-8",
            newline="",
        )


def test_canonical_semantic_hash_ignores_blank_node_ids_and_order():
    first = Graph().parse(
        data="""
            <https://example.test/s> <https://example.test/p> _:first .
            _:first <https://example.test/q> "value" .
        """,
        format="nt",
    )
    second = Graph().parse(
        data="""
            _:different <https://example.test/q> "value" .
            <https://example.test/s> <https://example.test/p> _:different .
        """,
        format="nt",
    )
    assert reasoner.canonical_graph_bytes(first) == reasoner.canonical_graph_bytes(second)
    assert reasoner.reasoner_input_semantic_hash(first) == reasoner.reasoner_input_semantic_hash(second)


def test_reasoner_input_is_identical_across_two_builds(tmp_path: Path):
    first = tmp_path / "first.nt"
    second = tmp_path / "second.nt"
    _, first_semantic, first_file = reasoner.write_reasoner_input(first)
    _, second_semantic, second_file = reasoner.write_reasoner_input(second)
    assert first.read_bytes() == second.read_bytes()
    assert first_semantic == second_semantic
    assert first_file == second_file
    assert first_file == reasoner.sha256_file(first)


def test_release_hash_excludes_optional_alignment_content_by_default(tmp_path: Path):
    _write_minimal_release(tmp_path)
    default_before = reasoner.ontology_release_source_hash(tmp_path)
    aligned_before = reasoner.ontology_release_source_hash(
        tmp_path,
        include_alignments=True,
    )
    (tmp_path / "ontology" / "alignments.ttl").write_text(
        "<https://example.test/A> <https://example.test/aligned> <https://external.test/CHANGED> .\n",
        encoding="utf-8",
    )
    assert reasoner.ontology_release_source_hash(tmp_path) == default_before
    assert (
        reasoner.ontology_release_source_hash(tmp_path, include_alignments=True)
        != aligned_before
    )


def test_release_hash_normalizes_line_endings(tmp_path: Path):
    _write_minimal_release(tmp_path, newline="\r\n")
    windows_hash = reasoner.ontology_release_source_hash(tmp_path)
    for path in reasoner.release_source_files(tmp_path):
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    assert reasoner.ontology_release_source_hash(tmp_path) == windows_hash
