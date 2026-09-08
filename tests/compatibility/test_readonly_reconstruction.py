"""Historical byte reconstruction does not expose another product writer."""
import importlib.util
import inspect

import pytest

from kg_mnp.compilation import compiler
from kg_mnp.graphdb.package_builder import build_graphdb_import_package
from kg_mnp.publication.package_builder import build_end_to_end_publication_package
from kg_mnp.webvowl.package_builder import build_webvowl_visualization_package
from kg_mnp.workbench import manifest


def test_old_compilation_has_no_writable_entrypoint():
    assert not hasattr(compiler, "compile_formal_semantics")


def test_old_workbench_has_no_writable_entrypoint():
    assert not hasattr(manifest, "build_workbench_package")


def test_only_current_application_service_is_available():
    assert importlib.util.find_spec("kg_mnp.application.service") is None


def test_historical_governance_has_no_writable_store():
    from kg_mnp.governance import workspace
    from scripts import governance_controlled_fixture

    assert not hasattr(workspace, "GovernanceWorkspaceStore")
    assert not hasattr(governance_controlled_fixture, "ControlledGovernanceWorkspaceStoreForTestHarness")


def test_historical_activation_has_no_state_controller_or_live_verifier():
    for module in ("persistence", "execution", "resolver"):
        assert importlib.util.find_spec("kg_mnp.activation." + module) is None


@pytest.mark.parametrize("builder", [build_graphdb_import_package,
                                    build_end_to_end_publication_package,
                                    build_webvowl_visualization_package])
def test_historical_builders_accept_no_output_or_force(builder):
    parameters = inspect.signature(builder).parameters
    assert "output_dir" not in parameters
    assert "force" not in parameters
    assert not any(p.kind == p.VAR_KEYWORD for p in parameters.values())
