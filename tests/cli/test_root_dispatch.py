"""One public command dispatcher; no importable alternate HTTP servers."""
import importlib.util

import pytest

from kg_mnp import root_cli
from kg_mnp.contracts import cli as contracts_cli
from kg_mnp.services import cli as service_cli


def test_root_routes_current_authorities_and_preserves_arguments(monkeypatch):
    calls = []
    monkeypatch.setattr(contracts_cli, "main", lambda argv: calls.append(("contracts", argv)) or 19)
    monkeypatch.setattr(service_cli, "main", lambda argv: calls.append(("service", argv)) or 23)
    assert root_cli.main(["contracts", "list"]) == 19
    assert root_cli.main(["service", "worker", "--once"]) == 23
    assert calls == [("contracts", ["list"]), ("service", ["worker", "--once"])]
    assert root_cli.main(["proposal", "validate"]) == 2
    assert len(calls) == 2


@pytest.mark.parametrize("module", [
    "application.http", "application.cli", "workbench.runtime", "workbench.cli",
    "diagnostics.runtime", "diagnostics.cli", "governance.runtime", "governance.cli",
])
def test_removed_servers_cannot_be_imported_as_alternate_product_entrypoints(module):
    assert importlib.util.find_spec("kg_mnp." + module) is None
