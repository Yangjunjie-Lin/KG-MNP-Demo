"""Legacy module-execution entry, delegating to the sole current CLI."""
from zhigou_toolchain.root_cli import main

__all__ = ["main"]

if __name__ == "__main__":
    from . import legacy_main
    raise SystemExit(legacy_main())
