from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from kg_mnp_demo import root_cli
from kg_mnp_demo.activation import cli
from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.activation.runtime import ActivationRuntimeConfig
from kg_mnp_demo.modeling import cli as modeling_cli

RUNTIME_ARGUMENTS = [
    "--publication-package",
    "publication",
    "--publication-attestation",
    "publication-attestation.json",
    "--phase01-artifact-dir",
    "phase01",
    "--phase02-artifact-dir",
    "phase02",
    "--phase03-artifact-dir",
    "phase03",
    "--phase04-artifact-dir",
    "phase04",
    "--phase05-artifact-dir",
    "phase05",
    "--expected-commit-sha",
    "a" * 40,
]


def _parse(*arguments: str) -> argparse.Namespace:
    return cli._parser().parse_args([*arguments, *RUNTIME_ARGUMENTS])


def test_parser_exposes_only_the_phase06_human_workflow() -> None:
    parser = cli._parser()
    choices = next(
        action.choices
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert set(choices) == {
        "upstream",
        "registry",
        "status",
        "proposal",
        "review",
        "execute",
        "rollback",
        "resolve-current",
        "verify",
    }
    help_text = parser.format_help().casefold()
    for forbidden in (
        "force",
        " graph-update",
        " rdf-patch",
        " repository-delete",
        " compile",
        " semantic-confirm",
        "http service",
    ):
        assert forbidden not in help_text


def test_mutation_parsers_require_explicit_human_acknowledgements() -> None:
    create = [
        "proposal",
        "create",
        "--target-publication-id",
        "urn:publication:p1",
        "--rationale",
        "Select verified P1",
        "--created-by-label",
        "operator label",
        "--expected-registry-revision",
        "1",
        "--expected-head-event-hash",
        "b" * 64,
        *RUNTIME_ARGUMENTS,
    ]
    with pytest.raises(SystemExit):
        cli._parser().parse_args(create)

    review = [
        "review",
        "record",
        "--proposal-id",
        "urn:proposal",
        "--decision",
        "APPROVE_FOR_ACTIVATION",
        "--reviewed-by-label",
        "reviewer label",
        "--review-note",
        "Explicit deployment approval",
        "--expected-registry-revision",
        "2",
        "--expected-head-event-hash",
        "c" * 64,
        *RUNTIME_ARGUMENTS,
    ]
    with pytest.raises(SystemExit):
        cli._parser().parse_args(review)


@pytest.mark.parametrize("command", ["verify", "resolve-current"])
def test_trust_commands_require_external_registry_and_head_anchors(command) -> None:
    with pytest.raises(SystemExit):
        _parse(command)

    parsed = _parse(
        command,
        "--expected-registry-hash",
        "d" * 64,
        "--expected-head-event-hash",
        "e" * 64,
    )
    assert parsed.expected_registry_hash == "d" * 64
    assert parsed.expected_head_event_hash == "e" * 64


def test_runtime_config_comes_only_from_startup_options() -> None:
    arguments = _parse(
        "status",
        "--state-dir",
        "state",
        "--publication-scenario",
        "issue-resolution",
        "--graphdb-url",
        "http://localhost:7200",
    )
    config = cli._runtime_config(arguments)
    assert config == ActivationRuntimeConfig(
        publication_package_directory=Path("publication"),
        publication_attestation_path=Path("publication-attestation.json"),
        phase01_artifact_directory=Path("phase01"),
        phase02_artifact_directory=Path("phase02"),
        phase03_artifact_directory=Path("phase03"),
        phase04_artifact_directory=Path("phase04"),
        phase05_artifact_directory=Path("phase05"),
        expected_commit_sha="a" * 40,
        state_directory=Path("state"),
        publication_scenario="issue-resolution",
        graphdb_url="http://localhost:7200",
    )
    assert not hasattr(arguments, "authority")
    assert not hasattr(arguments, "registry")
    assert not hasattr(arguments, "pointer_path")
    assert not hasattr(arguments, "repository_semantic_hash")


class _Controller:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def create_proposal(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        self.calls.append(("create", args, kwargs))
        return {"status": "DRAFT"}

    def record_review(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        self.calls.append(("review", args, kwargs))
        return {"status": "APPROVED_FOR_ACTIVATION"}


def test_mutation_dispatch_fixes_kind_and_passes_only_scalar_inputs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    controller = _Controller()
    configs: list[ActivationRuntimeConfig] = []
    monkeypatch.setattr(
        cli,
        "create_production_activation_controller",
        lambda config: configs.append(config) or controller,
    )
    create = _parse(
        "proposal",
        "create",
        "--target-publication-id",
        "urn:publication:p1",
        "--rationale",
        "Select verified P1",
        "--created-by-label",
        "operator label",
        "--explicit-human-intent",
        "--expected-registry-revision",
        "7",
        "--expected-head-event-hash",
        "b" * 64,
    )
    assert cli.dispatch_activation(create) == 0
    _, positional, payload = controller.calls[-1]
    assert positional == ()
    assert payload == {
        "target_publication_id": "urn:publication:p1",
        "activation_kind": "ACTIVATE_NEW_VERIFIED_PUBLICATION",
        "rationale": "Select verified P1",
        "created_by_label": "operator label",
        "explicit_human_intent": True,
        "expected_registry_revision": 7,
        "expected_head_event_hash": "b" * 64,
    }
    assert isinstance(configs[-1], ActivationRuntimeConfig)
    assert json.loads(capsys.readouterr().out) == {"status": "DRAFT"}

    review = _parse(
        "review",
        "record",
        "--proposal-id",
        "urn:proposal",
        "--decision",
        "APPROVE_FOR_ACTIVATION",
        "--reviewed-by-label",
        "reviewer label",
        "--review-note",
        "Explicit approval",
        "--explicit-human-action",
        "--expected-registry-revision",
        "8",
        "--expected-head-event-hash",
        "c" * 64,
    )
    assert cli.dispatch_activation(review) == 0
    name, positional, payload = controller.calls[-1]
    assert name == "review"
    assert positional == ("urn:proposal",)
    assert payload["explicit_human_action"] is True
    assert set(payload) == {
        "decision",
        "reviewed_by_label",
        "review_note",
        "explicit_human_action",
        "expected_registry_revision",
        "expected_head_event_hash",
    }


def test_main_serializes_activation_errors_canonically(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "dispatch_activation",
        lambda _arguments: (_ for _ in ()).throw(
            ActivationError(ActivationErrorCode.ACTIVATION_CONCURRENCY_CONFLICT)
        ),
    )
    assert cli.main(["status", *RUNTIME_ARGUMENTS]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "code": "ACTIVATION_CONCURRENCY_CONFLICT",
        "detail": "ACTIVATION_CONCURRENCY_CONFLICT",
        "status": "FAILED",
    }


def test_root_cli_routes_only_the_activation_first_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        cli,
        "main",
        lambda argv: calls.append(("activation", argv)) or 17,
    )
    monkeypatch.setattr(
        modeling_cli,
        "main",
        lambda argv: calls.append(("foundation", argv)) or 23,
    )
    assert root_cli.main(["activation", "status"]) == 17
    assert root_cli.main(["contracts", "list"]) == 23
    assert calls == [
        ("activation", ["status"]),
        ("foundation", ["contracts", "list"]),
    ]
