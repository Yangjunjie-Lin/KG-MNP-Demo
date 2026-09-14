"""Fail-closed research isolation preflight, not a claimed OS sandbox.

No user account, firewall or Docker service is modified. Until the existing
application can be launched in a verified minimal OS environment, full LIVE
runs must be blocked. Python allowlists are not operating-system permissions.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def probe_isolation():
    executable = shutil.which("docker")
    available = False
    if executable:
        try:
            result = subprocess.run([executable, "info", "--format", "{{.ServerVersion}}"], capture_output=True, timeout=15, check=False)
            available = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    # Actual benign canary: demonstrate whether this ordinary worker process
    # can read a sibling scoring directory. No real gold or secret is touched.
    denied = None
    with tempfile.TemporaryDirectory(prefix="ontology-io-canary-") as temporary:
        root = Path(temporary)
        (root / "generation").mkdir()
        (root / "scoring").mkdir()
        (root / "scoring/canary.txt").write_text("SYNTHETIC_CANARY_NOT_GOLD", encoding="utf-8")
        try:
            check = subprocess.run([sys.executable, "-I", "-c",
                "from pathlib import Path; assert Path('../scoring/canary.txt').read_text() == 'SYNTHETIC_CANARY_NOT_GOLD'"],
                cwd=root / "generation", capture_output=True, timeout=15, check=False)
            denied = False if check.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"status": "BLOCKED_OS_ISOLATION", "docker_cli_present": executable is not None,
        "docker_server_available": available, "os_canary_access_denied": denied, "endpoint_egress_verified": False,
        "canary_scope": "BENIGN_SIBLING_SCORING_DIRECTORY_SAME_USER_PYTHON_ISOLATED_MODE",
        "reason": "VERIFIED_MINIMAL_MOUNT_AND_ENDPOINT_ONLY_WORKER_NOT_IMPLEMENTED",
        "strong_leakage_isolation": False}


def require_isolation(receipt):
    # There is deliberately no user-provided raw_gold_access=False bypass.
    # Future launcher must actually execute canary and egress probes, not just
    # extend this function to trust a JSON status flag.
    raise ValueError("BLOCKED_OS_ISOLATION")
