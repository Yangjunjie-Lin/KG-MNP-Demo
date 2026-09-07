from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_live_harness_uses_an_isolated_dynamic_graphdb_host_port() -> None:
    script = (ROOT / "scripts/workbench_integration.py").read_text(encoding="utf-8")
    assert "graphdb_port = _free_port()" in script
    assert "ports: !override" in script
    assert "_assert_port_free(7200)" not in script
    assert "GraphDBClient(base_url=graphdb_base_url" in script
    assert "ReadOnlyGraphDBClient(base_url=graphdb_base_url" in script
