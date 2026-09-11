from __future__ import annotations

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
    for path in (ROOT / "src" / "zhigou_toolchain" / "modeling").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in forbidden_definitions):
            matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []


def test_no_unscoped_application_frontend_or_legacy_http_api_was_added() -> None:
    for relative in (
        "graphdb-local",
        "webvowl",
        "frontend",
        "src/zhigou_toolchain/graphdb.py",
        ):
        assert not (ROOT / relative).exists()


def test_pure_generator_has_no_network_clock_random_or_llm_imports() -> None:
    path = ROOT / "src/zhigou_toolchain/modeling/proposal.py"
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
