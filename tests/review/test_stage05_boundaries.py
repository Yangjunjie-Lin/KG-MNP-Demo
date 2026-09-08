from __future__ import annotations

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
    for path in (ROOT / "src" / "kg_mnp" / "modeling").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in forbidden):
            matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []
    for relative in (
        "graphdb-local",
        "webvowl",
        "frontend",
        "src/kg_mnp/graphdb.py",
    ):
        assert not (ROOT / relative).exists()


def test_review_modules_avoid_clock_random_network_llm_imports():
    for relative in (
        "src/kg_mnp/modeling/review_log.py",
        "src/kg_mnp/modeling/confirmation.py",
        "src/kg_mnp/modeling/review_identifiers.py",
    ):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        assert not imports & {"httpx", "openai", "random", "requests", "socket", "time", "urllib"}
