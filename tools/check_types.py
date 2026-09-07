"""Pinned static analysis of the public application backend, with this Python."""
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
entry=root/'workbench/node_modules/pyright/index.js'
if not entry.is_file():
    raise SystemExit('Run npm ci --prefix workbench to install the pinned type checker')
raise SystemExit(subprocess.run(['node',str(entry),'--project',str(root/'pyrightconfig.json'),'--pythonpath',sys.executable],cwd=root,check=False).returncode)
