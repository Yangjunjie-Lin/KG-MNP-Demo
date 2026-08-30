from __future__ import annotations

from pathlib import Path

import yaml

from kg_mnp.paths import domain_pack_path, domain_packs_root, repository_root

ROOT = Path(__file__).resolve().parents[2]
MNP_REQUIRED_DIRECTORIES = {
    "ontology",
    "terminology",
    "mappings",
    "shapes",
    "rules",
    "competency_questions",
    "queries",
    "fixtures/data",
    "fixtures/inputs",
}
FORBIDDEN_TOP_LEVEL_AUTHORITIES = {
    "ontology",
    "data",
    "inputs",
    "mappings",
    "rules",
    "shapes",
    "competency_questions",
    "queries",
}


def _manifest(pack: str) -> dict[str, object]:
    value = yaml.safe_load((ROOT / "domain_packs" / pack / "pack.yaml").read_text())
    assert isinstance(value, dict)
    return value


def test_bootstrap_pack_layout_and_honest_statuses() -> None:
    assert _manifest("minimal")["status"] == "SCAFFOLD"
    assert _manifest("mnp")["status"] == "MIGRATED_BASELINE"
    assert _manifest("forestry")["status"] == "PLANNED"
    for pack in ("minimal", "mnp", "forestry"):
        manifest = _manifest(pack)
        assert manifest["provisional"] is True
        assert (ROOT / "domain_packs" / pack / "README.md").is_file()


def test_mnp_assets_have_one_authoritative_location() -> None:
    pack = ROOT / "domain_packs" / "mnp"
    assert all((pack / relative).is_dir() for relative in MNP_REQUIRED_DIRECTORIES)
    assert (pack / "ontology" / "kg-mnp.ttl").is_file()
    assert (pack / "fixtures" / "data" / "CASE-01-eligible.ttl").is_file()
    assert (pack / "fixtures" / "inputs" / "case01.json").is_file()
    assert all(not (ROOT / name).exists() for name in FORBIDDEN_TOP_LEVEL_AUTHORITIES)


def test_central_path_resolution_distinguishes_authorities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    assert repository_root() == ROOT
    assert domain_packs_root() == ROOT / "domain_packs"
    assert domain_pack_path("mnp") == ROOT / "domain_packs" / "mnp"
    with monkeypatch.context() as scoped:
        scoped.setenv("KG_MNP_WORKSPACE", str(tmp_path / "runtime-workspace"))
        from kg_mnp.paths import runtime_workspace_root

        assert runtime_workspace_root() == (tmp_path / "runtime-workspace").resolve()
    assert not (tmp_path / "runtime-workspace").exists()


def test_domain_pack_identifier_rejects_traversal() -> None:
    for value in ("", ".", "..", "../mnp", "nested/mnp", "nested\\mnp"):
        try:
            domain_pack_path(value)
        except ValueError:
            continue
        raise AssertionError(f"unsafe pack identifier accepted: {value!r}")
