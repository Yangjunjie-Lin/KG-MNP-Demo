"""Run the byte-pinned, read-only ontology token auditor (Python 3.12+)."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "ontology_usage_audit/token-audit-portable-v1/audit_tokens.py"),
        run_name="__main__",
    )
