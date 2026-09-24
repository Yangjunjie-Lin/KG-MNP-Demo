"""Full means the frozen task/sample/system/repeat inventory, never a subset."""
from copy import deepcopy

import pytest

from tests.upgrade.test_ontology_io_integrity import protocol, sample
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.ontology_io.cli import save
from zhigou_toolchain.ontology_io.live_exports import verify_full_inventory


def fixture(tmp_path):
    rows = [sample().model_copy(update={"sample_id": sid, "group_id": sid}).model_dump(mode="json") for sid in ("a", "b")]
    p, task = protocol(replicates=2), "fixture"
    save(tmp_path / "generation/inputs.json", rows)
    locks = {task: {"legacy_prepared": str(tmp_path), "lock": {"input_sha256": semantic_hash(rows)}, "effective_input_sha256": semantic_hash(rows)}}
    inputs = {(task, r["sample_id"]): r for r in rows}
    jobs = [{"task": task, "sample": r["sample_id"], "system": system, "replicate": rep}
        for r in rows for system in p.systems for rep in range(p.replicates)]
    return jobs, inputs, {task: p}, locks


def test_full_inventory_matches_frozen_public_inputs(tmp_path):
    values = fixture(tmp_path)
    verify_full_inventory(*values)


@pytest.mark.parametrize("mutation", ["remove_job", "duplicate", "remove_input", "change_input", "change_source", "empty"])
def test_no_success_subset_or_missing_denominator_is_finalized(tmp_path, mutation):
    jobs, inputs, protocols, locks = deepcopy(fixture(tmp_path))
    if mutation == "remove_job":
        jobs.pop()
    elif mutation == "duplicate":
        jobs.append(jobs[0])
    elif mutation == "remove_input":
        inputs.pop(("fixture", "a"))
    elif mutation == "change_input":
        inputs[("fixture", "a")]["text"] = "tampered"
    elif mutation == "change_source":
        save(tmp_path / "generation/inputs.json", [])
    else:
        jobs, inputs = [], {}
    with pytest.raises(ValueError):
        verify_full_inventory(jobs, inputs, protocols, locks)
