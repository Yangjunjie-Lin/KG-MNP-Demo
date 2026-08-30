from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from kg_mnp.contracts import ContractCatalog

ROOT = Path(__file__).resolve().parents[2]


def _run(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (sys.executable, *arguments),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_wheel_contains_catalog_and_schemas_and_loads_outside_source_tree(
    tmp_path: Path,
) -> None:
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    _run(
        "-m",
        "pip",
        "wheel",
        "--disable-pip-version-check",
        "--no-deps",
        "--no-build-isolation",
        ".",
        "-w",
        str(wheel_dir),
        cwd=ROOT,
    )
    wheels = tuple(wheel_dir.glob("kg_mnp_toolchain-*.whl"))
    assert len(wheels) == 1

    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
    expected = {
        "kg_mnp/contracts/catalog.json",
        "kg_mnp/contracts/catalog.lock.json",
        *(f"kg_mnp/contracts/{spec.resource_path}" for spec in ContractCatalog.load().specs),
    }
    assert expected <= names
    assert not any(name.startswith(("runtime_reports/", "runtime_outputs/")) for name in names)
    assert not any(name.startswith("domain_packs/") for name in names)
    assert not any("graphdb.license" in name.casefold() for name in names)

    target = tmp_path / "isolated-install"
    probe_cwd = tmp_path / "outside-source-tree"
    probe_cwd.mkdir()
    _run(
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-deps",
        "--target",
        str(target),
        str(wheels[0]),
        cwd=probe_cwd,
    )
    probe = "\n".join(
        (
            "import json, sys",
            f"sys.path.insert(0, {str(target)!r})",
            "from importlib import resources",
            "from kg_mnp.contracts import ContractCatalog, get_contract_schema",
            "catalog = ContractCatalog.load()",
            "schema = get_contract_schema('project-lock')",
            (
                "payload = {'count': len(catalog.specs), 'title': schema['title'], "
                "'catalog': resources.files('kg_mnp.contracts')"
                ".joinpath('catalog.json').is_file()}"
            ),
            "print(json.dumps(payload, sort_keys=True))",
        )
    )
    completed = _run("-I", "-c", probe, cwd=probe_cwd)
    assert json.loads(completed.stdout) == {
        "catalog": True,
        "count": 20,
        "title": "KG-MNP ProjectLock 1.0",
    }
