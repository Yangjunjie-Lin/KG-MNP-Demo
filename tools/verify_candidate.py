"""Fixed-source local release verification runner, never auto-publishes or tags."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--include-browser',action='store_true',help='run all real synthetic browser workflows')
    args=parser.parse_args()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise SystemExit('Final candidate verification requires a clean code freeze')
    before=set((ROOT/'runtime_logs/p09').glob('fixed-*'))
    subprocess.run([sys.executable,'tools/verify_release_candidate.py','prepare'],cwd=ROOT,check=True)
    created=set((ROOT/'runtime_logs/p09').glob('fixed-*'))-before
    if len(created)!=1:
        raise SystemExit('Could not identify unique verification directory')
    directory=created.pop()
    for partition in ('serial','parallel','summarize'):
        subprocess.run([sys.executable,'tools/verify_release_candidate.py',partition,'--run-dir',str(directory)],cwd=ROOT,check=True)
    from verify_release_candidate import run
    commands={
        'lint':[sys.executable,'-m','ruff','check','.'],
        'types':[sys.executable,'tools/check_types.py'],
        'compiler-contracts':[sys.executable,'tools/generate_compiler_contracts.py','--check'],
        'catalog':[sys.executable,'scripts/generate_contract_catalog.py','--check'],
        'frontend-lint':['node','workbench/node_modules/eslint/bin/eslint.js','workbench/src','--config','workbench/eslint.config.mjs'],
        'frontend-types':['node','workbench/node_modules/typescript/bin/tsc','--project','workbench/tsconfig.json','--noEmit'],
    }
    receipts={}
    for name,command in commands.items():
        receipts[name]=run(directory,name,command)
    if args.include_browser:
        receipts['browser']=run(directory,'browser',[sys.executable,'tools/run_browser_verification.py'])
    (directory/'non-pytest-summary.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    if any(receipt['exit_code'] for receipt in receipts.values()):
        raise SystemExit(1)
    print('Local verification completed; platform clean installs, distribution inspection and evidence equality remain separate required checks')


if __name__=='__main__':
    main()
