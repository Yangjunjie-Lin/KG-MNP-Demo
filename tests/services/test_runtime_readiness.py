"""Doctor reports present resources, not a stale gate or a made-up release verdict."""
import json
from pathlib import Path

from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


def test_missing_runtime_dependencies_are_distinct_and_do_not_disclose_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    service = ApplicationService(ServiceConfiguration(str(tmp_path), domain_packs_root=str(tmp_path / "missing-packs")))
    result = service.runtime_check()
    assert result["status"] == "INSPECTED"
    assert result["checks"]["contracts"] == "LOCK_VERIFIED"
    assert result["checks"]["domain_packs"]["status"] == "BLOCKED"
    assert result["checks"]["reasoner"] == "UNAVAILABLE"
    assert result["checks"]["java"] == "MISSING"
    assert result["checks"]["workbench"] == "BUNDLE_MISSING"
    assert "workbench_backend_gate" not in result
    assert str(tmp_path) not in json.dumps(result)


def test_invalid_reasoner_is_not_available_and_packs_are_actual(tmp_path):
    jar = tmp_path / "invalid.jar"
    jar.write_bytes(b"not a trusted reasoner")
    service = ApplicationService(ServiceConfiguration(str(tmp_path / "service"), reasoner_jar=str(jar),
        domain_packs_root=str(Path(__file__).resolve().parents[2] / "domain_packs")))
    result = service.runtime_check()
    assert result["checks"]["reasoner"] == "INVALID_OR_MISSING_BUNDLE"
    assert {pack["pack_id"] for pack in result["checks"]["domain_packs"]} >= {"minimal", "mnp", "forestry"}
    assert all(pack["lock_status"] == "VERIFIED" for pack in result["checks"]["domain_packs"])
