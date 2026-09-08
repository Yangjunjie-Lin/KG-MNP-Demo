"""Parallel orchestration never duplicates nodes or summarizes unfinished runs."""
from threading import Barrier, Lock

from tools.verify_candidate import backend_partitions


def test_disjoint_partitions_overlap_and_summary_follows_both(tmp_path):
    barrier, lock, completed = Barrier(2), Lock(), []
    def execute(directory, name, command):
        assert directory == tmp_path
        if name == "backend-summarize":
            assert sorted(completed) == ["parallel", "serial"]
            return {"exit_code": 1}
        partition = command[2]
        assert partition in {"serial", "parallel"}
        barrier.wait(timeout=5)
        with lock: completed.append(partition)
        return {"exit_code": 3 if partition == "parallel" else 0}
    result = backend_partitions(tmp_path, execute)
    assert sorted(result) == ["backend-parallel", "backend-serial", "backend-summarize"]
    assert result["backend-parallel"]["exit_code"] == 3
    assert result["backend-summarize"]["exit_code"] == 1
