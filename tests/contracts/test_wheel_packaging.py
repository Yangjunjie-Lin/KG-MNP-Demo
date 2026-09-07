from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from kg_mnp.contracts import ContractCatalog

ROOT = Path(__file__).resolve().parents[2]
CURRENT_CONTRACT_COUNT = len(ContractCatalog.load().specs)


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
    assert "kg_mnp/ingestion/executor.py" in names
    assert "kg_mnp/plugins/registry.py" in names
    assert "kg_mnp/plugins/builtin/manifests/plain-text-parser.json" in names
    assert "kg_mnp/modeling/control_plane/service.py" in names
    assert "kg_mnp/plugins/builtin/manifests/baseline-reuse-provider.json" in names
    assert "kg_mnp/semantic_kernel/resources/toolchain-compiler-policy-1.0.0.yaml" in names
    assert "kg_mnp/semantic_kernel/resources/toolchain-provenance-vocabulary.ttl" in names
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
            "import contextlib, io, json, sys",
            f"sys.path.insert(0, {str(target)!r})",
            "from importlib import resources",
            "from kg_mnp.contracts import ContractCatalog, get_contract_schema",
            "from kg_mnp.root_cli import main as root_main",
            "from kg_mnp.semantic_kernel.policy import load_compiler_policy",
            "catalog = ContractCatalog.load()",
            "schema = get_contract_schema('project-lock')",
            "def invoke(arguments):",
            "    try:",
            "        return root_main(arguments)",
            "    except SystemExit as exc:",
            "        return exc.code",
            "with contextlib.redirect_stdout(io.StringIO()):",
            "    assert invoke(['model', '--help']) == 0",
            "    assert invoke(['review', '--help']) == 0",
            "    assert invoke(['compile', '--help']) == 0",
            "    assert invoke(['package', '--help']) == 0",
            "policy = load_compiler_policy()",
            "vocabulary = resources.files('kg_mnp.semantic_kernel').joinpath('resources/toolchain-provenance-vocabulary.ttl')",
            (
                "payload = {'count': len(catalog.specs), 'title': schema['title'], "
                "'catalog': resources.files('kg_mnp.contracts')"
                ".joinpath('catalog.json').is_file(), 'compiler': policy['compiler_version'], "
                "'vocabulary': vocabulary.is_file()}"
            ),
            "print(json.dumps(payload, sort_keys=True))",
        )
    )
    completed = _run("-I", "-c", probe, cwd=probe_cwd)
    assert json.loads(completed.stdout) == {
        "catalog": True,
        "compiler": "0.5.1",
        "count": CURRENT_CONTRACT_COUNT,
        "title": "KG-MNP ProjectLock 1.0",
        "vocabulary": True,
    }
