"""Temporary build ownership is independent from deterministic artifact IDs."""
from pathlib import Path

import pytest

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.ingestion.transaction import IngestionTransaction
from kg_mnp.semantic_kernel.transaction import SemanticCompilationTransaction


def semantic(root):
    return SemanticCompilationTransaction(root, build_id=stable_urn("semantic-compilation-build", {"x": 1}),
                                          package_id=stable_urn("ontology-package", {"x": 1}))


@pytest.mark.parametrize("factory", [lambda root: IngestionTransaction(root, "a" * 64), semantic], ids=["ingestion", "semantic"])
def test_transaction_never_deletes_previous_staging_on_entry(tmp_path, factory):
    transaction = factory(tmp_path)
    stale = transaction.staging
    stale.mkdir(parents=True)
    (stale / "previous.txt").write_bytes(b"inspect-before-recovery")
    with transaction as active:
        assert active.staging != stale
        assert (stale / "previous.txt").read_bytes() == b"inspect-before-recovery"
    assert (stale / "previous.txt").read_bytes() == b"inspect-before-recovery"
    assert not active.staging.exists()


def test_semantic_entry_failure_releases_its_operation_lock(tmp_path, monkeypatch):
    original = Path.mkdir

    def fail(path, *args, **kwargs):
        if path.name == "package":
            raise OSError("injected staging failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail)
    transaction = semantic(tmp_path)
    with pytest.raises(OSError, match="injected staging failure"), transaction:
        raise AssertionError("body must not run")
    assert not (tmp_path / "tmp/locks/semantic-compilation.lock").exists()
    assert not transaction.staging.exists()
