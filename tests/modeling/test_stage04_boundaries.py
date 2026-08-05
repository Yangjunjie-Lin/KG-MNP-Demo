from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage04_does_not_implement_later_stage_builders_or_compilers() -> None:
    forbidden_definitions = (
        "def build_confirmed_modeling_package",
        "def auto_confirm",
        "def confirm_all",
        "def compile_owl",
        "def compile_shacl",
        "def compile_rdf",
    )
    matches = []
    for path in (ROOT / "src" / "kg_mnp_demo").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in forbidden_definitions):
            matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []


def test_central_cli_has_no_review_confirm_compile_or_store_commands() -> None:
    from kg_mnp_demo.modeling.cli import build_parser

    parser = build_parser()
    action = next(
        item for item in parser._actions if isinstance(item, argparse._SubParsersAction)
    )
    command_names = set(action.choices)
    for command in ("review", "confirm", "compile", "graphdb", "webvowl"):
        assert command not in command_names


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
