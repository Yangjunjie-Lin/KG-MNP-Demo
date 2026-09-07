"""Old product runtimes cannot remain alternative approval/write entry points."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('name',['application','workbench','diagnostics','governance','amendment','activation'])
def test_old_runtime_commands_report_retirement_without_starting(name):
    result=subprocess.run([sys.executable,'-m','kg_mnp.root_cli',name,'--help'],cwd=ROOT,capture_output=True,text=True,check=False)
    assert result.returncode==2
    assert 'CLI_RETIRED' in result.stdout


def test_old_workbench_builder_cannot_create_another_product_bundle(tmp_path):
    target=tmp_path/'must-not-exist'
    result=subprocess.run([sys.executable,'-m','kg_mnp.root_cli','workbench','package','build','--output-dir',str(target)],cwd=ROOT,capture_output=True,text=True,check=False)
    assert result.returncode==2 and not target.exists()


def test_old_governance_mutation_shortcuts_remain_unavailable():
    for action in ['repair','resolve','graph','rdf']:
        result=subprocess.run([sys.executable,'-m','kg_mnp.root_cli','governance',action],cwd=ROOT,capture_output=True,text=True,check=False)
        assert result.returncode!=0
