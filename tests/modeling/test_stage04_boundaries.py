from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage04_does_not_implement_compilers_or_auto_confirmation() -> None:
    """Proposal generation remains a review-only boundary after Stage 06."""

    forbidden_definitions = (
        "def auto_confirm",
        "def confirm_all",
        "def compile_owl",
        "def compile_shacl",
        "def compile_rdf",
        "def build_trig",
        "def graphdb_import",
        "def webvowl_export",
    )
    matches = []
    for path in (ROOT / "src" / "kg_mnp_demo" / "modeling").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in forbidden_definitions):
            matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []


def test_central_cli_exposes_compile_only_at_stage06_boundary() -> None:
    from kg_mnp_demo.modeling.cli import build_parser

    parser = build_parser()
    action = next(
        item for item in parser._actions if isinstance(item, argparse._SubParsersAction)
    )
    command_names = set(action.choices)
    assert "compile" in command_names
    for command in ("graphdb", "webvowl", "auto-confirm"):
        assert command not in command_names
    # Stage 05 introduces explicit human review and confirmation builders.
    assert "review" in command_names
    assert "confirm" in command_names
    assert "package" in command_names


def test_no_graphdb_webvowl_frontend_or_http_api_was_added() -> None:
    for relative in (
        "graphdb-local",
        "webvowl",
        "frontend",
        "src/kg_mnp_demo/graphdb.py",
        "src/kg_mnp_demo/webvowl.py",
        "src/kg_mnp_demo/api",
    ):
        assert not (ROOT / relative).exists()


def test_pure_generator_has_no_network_clock_random_or_llm_imports() -> None:
    path = ROOT / "src/kg_mnp_demo/modeling/proposal.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    assert not imports & {
        "httpx",
        "openai",
        "random",
        "requests",
        "socket",
        "time",
        "urllib",
    }
