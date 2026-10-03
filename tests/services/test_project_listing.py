"""Navigation reads one catalog without turning metadata into approval."""
from dataclasses import asdict

import pytest

from tests.services.test_prompt08_boundary import create, identity
from zhigou_toolchain.services import projects
from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import (
    OperationRequest,
    ProjectHandle,
    ServiceConfiguration,
)


def test_listing_uses_one_snapshot_for_all_handles(tmp_path, monkeypatch):
    handles = [ProjectHandle(f"p{i}", f"project {i}", str(tmp_path / "projects" / str(i))) for i in range(15)]
    calls = []

    def catalog(root):
        calls.append(root)
        assert len(calls) == 1, "Repeated history parsing or mixed catalog generations"
        return {"projects": {h.project_id: asdict(h) for h in handles}}

    monkeypatch.setattr(projects, "load_catalog", catalog)
    assert projects.list_projects(tmp_path) == sorted(handles, key=lambda h: h.project_id)
    assert calls == [tmp_path]


def test_listing_is_not_validation_and_next_validation_detects_tampering(tmp_path, monkeypatch):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    _, alice = identity(service)
    _, bob = identity(service, "bob")
    created = create(service, alice)
    handle = projects.get_project(service.root, created["project_id"])
    from pathlib import Path
    (Path(handle.root) / "project.lock.json").write_text('{}', encoding="utf-8")
    from zhigou_toolchain.services import facade
    original = facade.inspect_project

    def no_implicit_validation(*args):
        pytest.fail("Project navigation must not replay confirmed semantic history")

    monkeypatch.setattr(facade, "inspect_project", no_implicit_validation)
    rows = service.execute(OperationRequest("project.list"), alice).payload["projects"]
    assert len(rows) == 1 and rows[0]["status"] == "OPEN"
    assert rows[0]["validation_status"] == "NOT_RUN_BY_LIST_PROJECTION"
    assert "root" not in rows[0]
    assert service.execute(OperationRequest("project.list"), bob).payload["projects"] == []
    monkeypatch.setattr(facade, "inspect_project", original)
    assert service.execute(OperationRequest("project.open", created["project_id"]), alice).payload["status"] != "VALID"
    with pytest.raises(ServiceBoundaryError, match="not authorized"):
        service.execute(OperationRequest("project.open", created["project_id"]), bob)
    service.tokens.revoke(alice.token_id)
    with pytest.raises(ServiceBoundaryError) as error:
        service.execute(OperationRequest("project.list"), alice)
    assert error.value.code == "AUTH_TOKEN_REVOKED"


@pytest.mark.parametrize("mutation", ["id", "root"])
def test_single_snapshot_still_rejects_invalid_handle(tmp_path, monkeypatch, mutation):
    row = asdict(ProjectHandle("p", "project", str(tmp_path / "projects/p")))
    row["project_id" if mutation == "id" else "root"] = "other" if mutation == "id" else str(tmp_path.parent)
    monkeypatch.setattr(projects, "load_catalog", lambda root: {"projects": {"p": row}})
    with pytest.raises(ServiceBoundaryError) as error:
        projects.list_projects(tmp_path)
    assert error.value.code == "PROJECT_CATALOG_INVALID"
