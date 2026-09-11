"""Bounded incremental evidence with exact working-tree fingerprint, not release certification."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def fingerprint():
    raw = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT)
    paths = sorted(set(raw.decode().split('\0')) - {''})
    records = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths
               if (ROOT/p).is_file() and not p.startswith('docs/modeling/evidence/')
               and p != 'docs/modeling/five-stage-verification.json'}
    return hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest(), records


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    from verify_release_candidate import run

    directory=ROOT/'runtime_logs'/('five-stage-'+uuid4().hex)
    directory.mkdir(parents=True)
    start, files=fingerprint()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
    versions={}
    for name in ('pydantic','pandas','networkx','rdflib','pyshacl','httpx','FlagEmbedding','faiss-cpu','transformers'):
        try:
            versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name]='NOT_INSTALLED'
    npm='npm.cmd' if os.name=='nt' else 'npm'
    commands=[('ruff',[sys.executable,'-m','ruff','check','.']),
              ('python-types',[sys.executable,'tools/check_types.py']),
              ('frontend-lint',[npm,'--prefix','workbench','run','lint']),
              ('frontend-types',[npm,'--prefix','workbench','run','typecheck']),
              ('frontend-tests',[npm,'--prefix','workbench','test']),
              ('frontend-build',[npm,'--prefix','workbench','run','build']),
              ('incremental-backend',[sys.executable,'-m','pytest','tests/modeling/test_five_stage.py',
                 'tests/services/test_five_stage_service.py','tests/services/test_export_snapshot.py','tests/services/test_state_projection.py',
                 'tests/services/test_unified_service.py','tests/services/test_request_target_boundary.py',
                 'tests/workbench/test_current_client_boundaries.py'])]
    receipts={name:run(directory,name,command,pytest_run=name=='incremental-backend') for name,command in commands}
    end,_=fingerprint()
    report={'scope':'INCREMENTAL_ONLY_NOT_RELEASE_ACCEPTANCE','actual_tested_commit':head,
            'working_tree_dirty':dirty,'tested_source_digest':start,'final_source_digest':end,
            'source_unchanged_during_run':start==end,'source_files':files,
            'environment':{'python':sys.version,'platform':platform.platform(),'dependencies':versions},
            'commands':receipts,'status':'PASS' if start==end and all(r['exit_code']==0 for r in receipts.values()) else 'FAIL',
            'live_models':'NOT_RUN','full_backend':'SEPARATE_RUN_REQUIRED','full_five_stage_upgrade':'INCOMPLETE'}
    (directory/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'evidence':directory.relative_to(ROOT).as_posix(),'status':report['status'],'same_source':start==end}),flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
