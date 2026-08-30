from __future__ import annotations

import json

from prompt03_support import run_cli


def test_plugin_list_doctor_validate_snapshot_and_conformance_cli() -> None:
    listing = run_cli("plugin", "list", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    payload = json.loads(listing.stdout)
    assert payload["command"] == "plugin list"
    assert len(payload["result"]) == 13
    assert all(item["builtin"] for item in payload["result"])
    assert all(item["status"] == "ENABLED" for item in payload["result"])
    doctor = run_cli("plugin", "doctor", "--json")
    assert doctor.returncode == 0
    assert json.loads(doctor.stdout)["result"]["external_auto_import"] is False
    validate = run_cli("plugin", "validate", "plain-text-parser", "--json")
    assert validate.returncode == 0
    assert json.loads(validate.stdout)["result"]["valid"] is True
    snapshot = run_cli("plugin", "snapshot", "plain-text-parser", "--json")
    assert snapshot.returncode == 0
    assert json.loads(snapshot.stdout)["result"]["snapshot_id"].startswith(
        "urn:kg-mnp:plugin-snapshot:"
    )
    conformance = run_cli("plugin", "conformance", "plain-text-parser", "--json")
    assert conformance.returncode == 0, conformance.stdout + conformance.stderr
    assert json.loads(conformance.stdout)["result"]["status"] == "PASS"


def test_plugin_cli_errors_are_stable_and_suppress_traceback() -> None:
    result = run_cli("plugin", "inspect", "missing-plugin", "--json")
    assert result.returncode == 9
    payload = json.loads(result.stdout)
    assert payload["status"] == "ERROR"
    assert payload["code"] == 9
    assert "Traceback" not in result.stdout + result.stderr
