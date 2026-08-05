"""Stage 01 closure checks for CLI registration and legacy system exit."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _load_pyproject() -> dict:
    # Minimal TOML-ish parse for the scripts table without adding a dependency.
    text = _read_text("pyproject.toml")
    scripts: dict[str, str] = {}
    in_scripts = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project.scripts]":
            in_scripts = True
            continue
        if in_scripts:
            if stripped.startswith("[") and stripped.endswith("]"):
                break
            if not stripped or stripped.startswith("#"):
                continue
            match = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*"([^"]+)"\s*$', stripped)
            assert match is not None, f"unparseable script line: {stripped}"
            scripts[match.group(1)] = match.group(2)
    return {"scripts": scripts}


def test_kg_mnp_console_entry_removed():
    scripts = _load_pyproject()["scripts"]
    assert "kg-mnp" not in scripts


def test_kg_mnp_eligibility_console_entry_present():
    scripts = _load_pyproject()["scripts"]
    assert scripts.get("kg-mnp-eligibility") == "kg_mnp_demo.cli:main"


def test_legacy_cli_description_marks_legacy():
    from kg_mnp_demo.cli import build_parser

    parser = build_parser()
    description = (parser.description or "").lower()
    assert "legacy" in description
    assert "eligibility" in description


def test_legacy_cli_module_docstring_marks_legacy():
    import kg_mnp_demo.cli as cli

    assert cli.__doc__ is not None
    assert "legacy" in cli.__doc__.lower()
    assert "eligibility" in cli.__doc__.lower()


def test_frontend_absent():
    assert not (ROOT / "frontend").exists()


def test_old_docker_entrypoints_absent():
    for name in (
        "docker-compose.yml",
        "docker-compose.fullstack.yml",
        "docker-compose.api.yml",
        "Dockerfile",
    ):
        assert not (ROOT / name).exists(), name


def test_node_and_playwright_entrypoints_absent():
    for relative in (
        "frontend/package.json",
        "package.json",
        "frontend/playwright.config.ts",
        "playwright.config.ts",
    ):
        assert not (ROOT / relative).exists(), relative


def test_neo4j_and_api_dependencies_absent_from_pyproject():
    text = _read_text("pyproject.toml").lower()
    assert "neo4j" not in text
    assert "fastapi" not in text
    assert "uvicorn" not in text


def test_api_and_neo4j_packages_absent():
    assert not (ROOT / "src" / "kg_mnp_demo" / "api").exists()
    assert not (ROOT / "src" / "kg_mnp_demo" / "storage").exists()
    assert not (ROOT / "src" / "kg_mnp_demo" / "neo4j_pipeline.py").exists()
    assert not (ROOT / "src" / "kg_mnp_demo" / "neo4j_store.py").exists()


def test_readme_does_not_treat_eligibility_as_central_task():
    readme = _read_text("README.md").lower()
    assert "不以携号转网资格判断为中央任务" in _read_text("README.md") or (
        "eligibility" in readme and "central" in readme and "not" in readme
    )
    assert "ontology" in readme
    assert "kg-mnp-eligibility" in readme


def test_ontology_modules_catalog_still_loads():
    catalog = yaml.safe_load(_read_text("config/ontology_modules.yaml"))
    assert catalog
