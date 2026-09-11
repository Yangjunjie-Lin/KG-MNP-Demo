"""Current product registration, dependency policy and obsolete platform exit."""

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


def test_kg_mnp_console_entry_uses_the_application_aware_root_dispatcher():
    scripts = _load_pyproject()["scripts"]
    assert scripts.get("kg-mnp") == "kg_mnp:legacy_main"
    assert scripts.get("zhigou-toolchain") == "zhigou_toolchain.root_cli:main"


def test_domain_specific_eligibility_console_entry_is_not_public():
    scripts = _load_pyproject()["scripts"]
    assert "kg-mnp-eligibility" not in scripts


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


def test_no_neo4j_and_current_http_dependency_is_exactly_locked():
    text = _read_text("pyproject.toml").lower()
    assert "neo4j" not in text
    import tomllib
    project = tomllib.loads(text)
    locked = _read_text("requirements-dev.lock").lower().splitlines()
    fastapi = next(pin for pin in project["project"]["dependencies"] if pin.startswith("fastapi=="))
    assert fastapi in locked
    assert '"uvicorn==0.30.6"' in text
    assert (ROOT / "src/zhigou_toolchain/api/app.py").is_file()


def test_service_api_is_explicit_and_neo4j_packages_absent():
    # The original Stage 01 closure predated the Prompt 07 service boundary.
    # Keep its storage/Neo4j prohibition while allowing the explicit API layer
    # introduced by the unified service architecture.
    assert (ROOT / "src" / "zhigou_toolchain" / "api" / "app.py").is_file()
    assert not (ROOT / "src" / "zhigou_toolchain" / "storage").exists()
    assert not (ROOT / "src" / "zhigou_toolchain" / "neo4j_pipeline.py").exists()
    assert not (ROOT / "src" / "zhigou_toolchain" / "neo4j_store.py").exists()


def test_readme_does_not_treat_eligibility_as_central_task():
    readme = _read_text("README.md").lower()
    assert "独立领域包" in _read_text("README.md")
    assert "ontology" in readme
    assert "toolchain" in readme


def test_ontology_modules_catalog_still_loads():
    catalog = yaml.safe_load(
        _read_text("domain_packs/mnp/ontology/modules.yaml")
    )
    assert catalog
