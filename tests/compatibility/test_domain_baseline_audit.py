"""The preservation tool cannot redefine its expected baseline from live files."""
import hashlib
import shutil
import subprocess

import pytest

from tools import check_domain_baselines
from tools.check_domain_baselines import ROOT, check
from zhigou_toolchain.domain_packs.locking import DomainPackLockError
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry


def test_domain_baseline_check_reads_original_history_and_never_rewrites_assets():
    paths = [ROOT / "tests/golden/domain-packs/mnp-prompt01-content.json"]
    paths += [path for path in (ROOT / "domain_packs").rglob("*") if path.is_file()]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert check() == {"status": "PRESERVED", "mnp_original_assets": 84, "read_only": True,
        "verified_pack_versions": ["empty@0.1.0", "forestry@0.2.0", "forestry-workorders@0.1.0",
            "forestry-workorders@0.1.1", "hr@0.1.0", "minimal@0.1.0", "mnp@1.0.0"]}
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths} == before


@pytest.mark.parametrize("relative", ["hr", "forestry-workorders", ".versions/0.1.0/forestry-workorders"])
def test_preservation_gate_rejects_new_or_archived_manifest_byte_drift(tmp_path, monkeypatch, relative):
    packs = tmp_path / "packs"
    shutil.copytree(ROOT / "domain_packs", packs)
    manifest = packs / relative / "pack.yaml"
    original = manifest.read_bytes()
    normalized = original.replace(b"\r\n", b"\n")
    assert original != normalized  # The regression is a byte-only change.
    manifest.write_bytes(normalized)
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in packs.rglob("*") if p.is_file()}
    monkeypatch.setattr(check_domain_baselines, "DomainPackRegistry", lambda _root: DomainPackRegistry(packs))
    with pytest.raises(DomainPackLockError, match="lock mismatch"):
        check()
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before} == before


@pytest.mark.parametrize("autocrlf", ["true", "false"])
def test_all_pack_locks_survive_fresh_git_checkout(tmp_path, autocrlf):
    source = tmp_path / "source"
    source.mkdir()
    shutil.copyfile(ROOT / ".gitattributes", source / ".gitattributes")
    shutil.copytree(ROOT / "domain_packs", source / "domain_packs")
    def git(*args):
        subprocess.run(["git", "-c", f"core.autocrlf={autocrlf}", "-c", "core.safecrlf=false", *args],
            cwd=source, check=True, capture_output=True, timeout=60)
    git("init", "--quiet")
    git("add", ".gitattributes", "domain_packs")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git("checkout-index", "--all", "--prefix=" + checkout.as_posix() + "/")
    registry = DomainPackRegistry(checkout / "domain_packs")
    expected = DomainPackRegistry(ROOT / "domain_packs")
    assert len(registry.list()) == len(expected.list())
    for pack_id, version, _path in registry.list():
        assert registry.resolve(pack_id, version).lock.document == expected.resolve(pack_id, version).lock.document
