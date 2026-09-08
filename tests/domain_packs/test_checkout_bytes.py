"""Git checkout conversion must not invalidate locked text/CSV asset bytes."""
import subprocess
from pathlib import Path

from kg_mnp.domain_packs.registry import DomainPackRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_windows_autocrlf_filter_preserves_every_forestry_locked_asset():
    pack = DomainPackRegistry(ROOT / "domain_packs").resolve("forestry", "0.2.0")
    for asset in pack.manifest.document["assets"]:
        relative = "domain_packs/forestry/" + asset["path"]
        filtered = subprocess.check_output(["git", "-c", "core.autocrlf=true", "cat-file", "--filters", "HEAD:" + relative], cwd=ROOT)
        assert filtered == (ROOT / relative).read_bytes(), relative
