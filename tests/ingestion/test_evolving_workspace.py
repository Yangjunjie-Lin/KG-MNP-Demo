"""Further source ingestion must preserve already confirmed/compiled bytes."""
import shutil

from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.planner import create_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore
from kg_mnp.services.projects import get_project
from tests.services.test_modeling_workflow import (
    modeling_case,  # noqa: F401 - imported pytest fixture
    run_confirmed_initial_chain,
)


def test_ingestion_after_confirmation_keeps_formal_artifacts(modeling_case, tmp_path):  # noqa: F811 - real service fixture
    case = run_confirmed_initial_chain(modeling_case)
    root = tmp_path / "workspace"
    # Copy a genuinely published Workspace with the current deterministic
    # confirmation layout, not the compiler unit fixture's ad-hoc input folder.
    shutil.copytree(get_project(case["service"].root, case["project_id"]).root, root)
    formal = [root / "artifacts/confirmed", root / "artifacts/packages"]
    before = {p.relative_to(root).as_posix(): p.read_bytes() for d in formal for p in d.rglob("*") if p.is_file()}
    assert before
    source = tmp_path / "second.csv"
    source.write_bytes(b"entity,label\nsecond,Second synthetic entity\n")
    store = SourceStore(root)
    registered = store.add_file(source)
    batch = store.create_batch((registered.source["source_id"],))
    plan = create_ingestion_plan(root, batch_id=batch["batch_id"])
    result = execute_ingestion_plan(root, plan.plan["plan_id"])
    assert result.run["status"] == "SUCCEEDED"
    assert result.dataset["items"] and result.dataset["evidence_records"]
    after = {p.relative_to(root).as_posix(): p.read_bytes() for d in formal for p in d.rglob("*") if p.is_file()}
    assert after == before
