"""One-time source migrations are history, not current product entry points."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETIRED = (
    "tools/consolidation_audit.py",
    "scripts/build_ontology_release.py",
    "scripts/stage03_term.py",
    "scripts/stage03_term_catalog_part2.py",
    "scripts/stage03_term_catalog_part3.py",
    "scripts/stage03_term_catalog_part4.py",
    "scripts/stage03_constants.py",
    "scripts/migrate_ontology_iris.py",
    "scripts/rewrite_case_semantics.py",
    "scripts/normalize_domain_pack_text.py",
    "scripts/generate_competency_questions.py",
    "scripts/prompt03_cli_smoke.py",
)


def test_one_time_writers_cannot_rewrite_frozen_assets_or_requirement_evidence():
    assert not [name for name in RETIRED if (ROOT / name).exists()]


def test_install_target_uses_only_declared_dependency_extras():
    import re
    import tomllib

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    available = set(metadata["project"]["optional-dependencies"])
    extras = re.findall(r'\.\[([^\]]+)\]', (ROOT / "Makefile").read_text(encoding="utf-8"))
    assert extras
    assert all(set(value.split(",")) <= available for value in extras)


def test_readonly_ontology_check_uses_the_shared_current_namespace():
    import runpy

    from kg_mnp.namespaces import BASE

    checker = runpy.run_path(str(ROOT / "scripts/check_ontology_release.py"))
    assert checker["TERM_NS"] == BASE
    assert checker["main"]() == 0
