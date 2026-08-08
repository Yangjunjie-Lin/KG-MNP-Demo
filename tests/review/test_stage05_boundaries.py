from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage05_forbids_compilers_auto_confirm_and_integrations():
    forbidden = (
        "def auto_confirm",
        "def confirm_all",
        "def compile_owl",
        "def compile_shacl",
        "def compile_rdf",
        "def build_trig",
        "def graphdb_import",
        "def webvowl_export",
        "def llm_reviewer",
    )
    matches = []
    for path in (ROOT / "src" / "kg_mnp_demo" / "modeling").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in forbidden):
            matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []
    for relative in (
        "graphdb-local",
        "webvowl",
        "frontend",
        "src/kg_mnp_demo/graphdb.py",
        "src/kg_mnp_demo/api",
    ):
        assert not (ROOT / relative).exists()


def test_cli_preserves_review_confirm_after_final_extensions():
    from kg_mnp_demo.modeling.cli import build_parser

    parser = build_parser()
    action = next(
        item for item in parser._actions if isinstance(item, argparse._SubParsersAction)
    )
    names = set(action.choices)
    assert {"review", "confirm", "package"} <= names
    assert "compile" in names
    assert "graphdb" in names
    assert {"webvowl", "publication"} <= names
    assert "auto-confirm" not in names
    review = action.choices["review"]
    review_action = next(
        item for item in review._actions if isinstance(item, argparse._SubParsersAction)
    )
    assert not {"auto", "recommend"} & set(review_action.choices)


def test_review_modules_avoid_clock_random_network_llm_imports():
    for relative in (
        "src/kg_mnp_demo/modeling/review_log.py",
        "src/kg_mnp_demo/modeling/confirmation.py",
        "src/kg_mnp_demo/modeling/review_identifiers.py",
    ):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        assert not imports & {"httpx", "openai", "random", "requests", "socket", "time", "urllib"}
