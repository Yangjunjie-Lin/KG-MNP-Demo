"""The preservation tool cannot redefine its expected baseline from live files."""
import hashlib

from tools.check_domain_baselines import ROOT, check


def test_domain_baseline_check_reads_original_history_and_never_rewrites_assets():
    paths = [ROOT / "tests/golden/domain-packs/mnp-prompt01-content.json"]
    paths += [path for name in ("minimal", "mnp") for path in (ROOT / "domain_packs" / name).rglob("*") if path.is_file()]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert check() == {"status": "PRESERVED", "mnp_original_assets": 84, "read_only": True}
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths} == before
