"""CLI smoke tests (offline RDF backend)."""

import json

from kg_mnp_demo.cli import main


def test_cli_evaluate_case_03(capsys):
    code = main(["evaluate", "--case", "CASE-03", "--backend", "rdf"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["case_id"] == "CASE-03"
    assert out["decision"] == "BLOCKED"
    assert out["backend"] == "rdf"
    assert "tmf_mappings_used" in out
    assert "ontology_sources" in out


def test_cli_mappings(capsys):
    assert main(["mappings"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mappings"]


def test_cli_sources(capsys):
    assert main(["sources"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sources"]


def test_cli_run_all_twice_consistent(capsys):
    assert main(["run-all", "--backend", "rdf"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["run-all", "--backend", "rdf"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first == second
    assert first["run_all"]["CASE-01"]["decision"] == "ELIGIBLE"
    assert first["run_all"]["CASE-02"]["decision"] == "BLOCKED"
    assert first["run_all"]["CASE-05"]["decision"] == "MANUAL_REVIEW"


def test_cli_neo4j_up(capsys):
    assert main(["neo4j-up"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["compose_file"] == "docker-compose.yml"
