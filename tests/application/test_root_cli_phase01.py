from __future__ import annotations

import json

from kg_mnp_demo import root_cli
from kg_mnp_demo.application import cli as application_cli
from kg_mnp_demo.modeling import cli as modeling_cli


def test_root_cli_routes_only_application_first_token(monkeypatch) -> None:
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        application_cli,
        "main",
        lambda argv: calls.append(("application", argv)) or 17,
    )
    monkeypatch.setattr(
        modeling_cli,
        "main",
        lambda argv: calls.append(("foundation", argv)) or 23,
    )

    assert root_cli.main(["application", "query", "list"]) == 17
    assert root_cli.main(["contracts", "list"]) == 23
    assert calls == [
        ("application", ["query", "list"]),
        ("foundation", ["contracts", "list"]),
    ]


def test_application_runtime_parsers_require_a_controlled_scenario(capsys) -> None:
    common = [
        "--publication-package",
        "package",
        "--attestation",
        "publication-attestation.json",
    ]
    valid = application_cli.build_parser().parse_args(
        [
            "runtime",
            "check",
            *common,
            "--publication-scenario",
            "issue-resolution",
        ]
    )
    assert valid.publication_scenario == "issue-resolution"

    assert application_cli.main(["runtime", "check", *common]) == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "INVALID_PARAMETER"


def test_query_run_checks_runtime_before_executing(monkeypatch) -> None:
    calls: list[str] = []

    class Service:
        def runtime_check(self):
            calls.append("runtime_check")
            return {"status": "APPLICATION_READY"}

        def run(self, query_id, parameters):
            calls.append(f"run:{query_id}")
            return {"query_id": query_id, "parameters": parameters}

    monkeypatch.setattr(application_cli, "_service", lambda args: Service())
    monkeypatch.setattr(application_cli, "_json_print", lambda payload, **kwargs: None)
    args = application_cli.build_parser().parse_args(
        [
            "query",
            "run",
            "provenance.fact",
            "--publication-package",
            "package",
            "--attestation",
            "publication-attestation.json",
            "--publication-scenario",
            "full-confirmation",
        ]
    )

    assert application_cli.dispatch_application(args) == 0
    assert calls == ["runtime_check", "run:provenance.fact"]


def test_serve_checks_runtime_before_starting_server(monkeypatch) -> None:
    calls: list[str] = []

    class Service:
        def runtime_check(self):
            calls.append("runtime_check")
            return {"status": "APPLICATION_READY"}

    monkeypatch.setattr(application_cli, "_service", lambda args: Service())
    monkeypatch.setattr(
        application_cli,
        "create_app",
        lambda service: calls.append("create_app") or object(),
    )
    monkeypatch.setattr(
        "uvicorn.run",
        lambda app, **kwargs: calls.append("uvicorn.run"),
    )
    args = application_cli.build_parser().parse_args(
        [
            "serve",
            "--publication-package",
            "package",
            "--attestation",
            "publication-attestation.json",
            "--publication-scenario",
            "modified-confirmation",
        ]
    )

    assert application_cli.dispatch_application(args) == 0
    assert calls == ["runtime_check", "create_app", "uvicorn.run"]
