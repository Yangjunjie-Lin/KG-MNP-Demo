"""Further source ingestion must preserve already confirmed/compiled bytes."""
import shutil

from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.planner import create_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore


def test_ingestion_after_confirmation_keeps_formal_artifacts(prompt05_case, tmp_path):
    root = tmp_path / "workspace"
    shutil.copytree(prompt05_case["workspace"], root)
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
