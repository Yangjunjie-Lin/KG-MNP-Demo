"""Run actual browser workflows against an owned synthetic server and Worker."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    server=subprocess.Popen([sys.executable,str(ROOT/'tools/run_workbench_test_server.py'),'--temporary-pack'],cwd=ROOT,stdout=subprocess.PIPE,text=True,creationflags=flags)
    try:
        line=server.stdout.readline()
        if not line:
            raise SystemExit('Synthetic browser server failed before readiness')
        ready=json.loads(line)
        environment={**os.environ,'KG_MNP_BROWSER_URL':ready['url'],'KG_MNP_BROWSER_CREDENTIAL':ready['credential_path']}
        npm='npm.cmd' if os.name=='nt' else 'npm'
        result=subprocess.run([npm,'--prefix','workbench','run','test:e2e'],cwd=ROOT,env=environment,check=False)
        raise SystemExit(result.returncode)
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)


if __name__=='__main__':
    main()
