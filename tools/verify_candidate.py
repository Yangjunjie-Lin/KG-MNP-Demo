"""Fixed-source local release verification runner, never auto-publishes or tags."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--include-browser',action='store_true',help='compatibility flag; real browser verification is always required')
    parser.parse_args()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise SystemExit('Final candidate verification requires a clean code freeze')
    before=set((ROOT/'runtime_logs/p09').glob('fixed-*'))
    subprocess.run([sys.executable,'tools/verify_release_candidate.py','prepare'],cwd=ROOT,check=True)
    created=set((ROOT/'runtime_logs/p09').glob('fixed-*'))-before
    if len(created)!=1:
        raise SystemExit('Could not identify unique verification directory')
    directory=created.pop()
    from verify_release_candidate import assert_frozen, run
    plan=json.loads((directory/'plan.json').read_bytes())
    npm='npm.cmd' if os.name=='nt' else 'npm'
    commands={
        'python-environment':[sys.executable,'-m','pip','check'],
        'python-version':[sys.executable,'--version'],
        'node-version':['node','--version'],
        'java-version':['java','-version'],
        'frontend-install':[npm,'--prefix','workbench','ci','--no-fund'],
        'lint':[sys.executable,'-m','ruff','check','.'],
        'types':[sys.executable,'tools/check_types.py'],
        'compiler-contracts':[sys.executable,'tools/generate_compiler_contracts.py','--check'],
        'catalog':[sys.executable,'scripts/generate_contract_catalog.py','--check'],
        'frontend-lint':[npm,'--prefix','workbench','run','lint'],
        'frontend-types':[npm,'--prefix','workbench','run','typecheck'],
        'frontend-unit':[npm,'--prefix','workbench','test'],
        'frontend-build':[npm,'--prefix','workbench','run','build'],
        'browser-collection':[npm,'--prefix','workbench','run','test:e2e','--','--list'],
        'repository-hygiene':[sys.executable,'scripts/check_repo_hygiene.py'],
    }
    receipts={}
    for name,command in commands.items():
        assert_frozen(plan)
        receipts[name]=run(directory,name,command)
        assert_frozen(plan)
    # Distribution tests consume generated static assets, so building the one
    # current frontend must precede backend execution, never reuse an old dist.
    if all(receipt['exit_code']==0 for receipt in receipts.values()):
        for partition in ('serial','parallel','summarize'):
            receipts['backend-'+partition]=run(directory,'backend-'+partition,[sys.executable,'tools/verify_release_candidate.py',partition,'--run-dir',str(directory)])
        assert_frozen(plan)
        receipts['browser']=run(directory,'browser',[sys.executable,'tools/run_browser_verification.py'])
        assert_frozen(plan)
        receipts['distribution']=run(directory,'distribution',[sys.executable,'tools/verify_distribution.py','--output',str(directory/'distribution-evidence')])
        assert_frozen(plan)
    else:
        receipts['required-workflows']={'exit_code':1,'status':'NOT_RUN_PREPARATION_FAILED'}
    (directory/'non-pytest-summary.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    if any(receipt['exit_code'] for receipt in receipts.values()):
        raise SystemExit(1)
    print('Current-platform capability and distribution checks completed. Other-platform evidence, manual visual/keyboard review and delivery equality are still mandatory; this command does not approve a release tag.')


if __name__=='__main__':
    main()
