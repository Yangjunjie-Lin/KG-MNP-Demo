"""Read-only v3/native inspection and explicitly non-v3 diagnostic export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .native import diagnostic_bytes, inspect_native
from .v3 import V3Delivery, read_zip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("archive", type=Path)
    inspect.add_argument("--shacl", action="store_true")
    preflight = sub.add_parser("preflight-native")
    preflight.add_argument("archive", type=Path)
    diagnostic = sub.add_parser("export-diagnostic")
    diagnostic.add_argument("archive", type=Path)
    diagnostic.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "inspect":
        result = V3Delivery(read_zip(args.archive.read_bytes())).inspect(run_shacl=args.shacl)
    elif args.command == "preflight-native":
        result = inspect_native(args.archive)
    else:
        data = diagnostic_bytes(args.archive)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            stream.write(data)
        result = {"status": "DIAGNOSTIC_EXPORTED", "v3_export_created": False, "release_status": "NOT_RELEASED"}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
