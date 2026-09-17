"""Read-only v3/native inspection and explicitly non-v3 diagnostic export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .exchange_io import (
    atomic_file,
    json_bytes,
    read_bounded,
    read_directory,
    write_directory,
)
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
    handoff = sub.add_parser("export-handoff", help="Download an already committed authorized service export")
    handoff.add_argument("output", type=Path)
    handoff.add_argument("--workspace", type=Path, required=True)
    handoff.add_argument("--project-id", required=True)
    handoff.add_argument("--job-id", required=True)
    check_handoff = sub.add_parser("validate-handoff")
    check_handoff.add_argument("archive", type=Path)
    check_handoff.add_argument("--receipt", type=Path, help="Out-of-band authorized service export result, not a bundled self-assertion")
    check_stage = sub.add_parser("validate-stage")
    check_stage.add_argument("archive", type=Path)
    check_stage.add_argument("--sha256", help="Trusted out-of-band digest of the complete final ZIP")
    check_stage.add_argument("--replay-negatives", action="store_true")
    check_evolution = sub.add_parser("validate-evolution")
    check_evolution.add_argument("directory", type=Path)
    check_evolution.add_argument("--producer", action="store_true")
    export_evolution = sub.add_parser("export-evolution")
    export_evolution.add_argument("trace", type=Path, nargs="+")
    export_evolution.add_argument("--output", type=Path, required=True)
    export_evolution.add_argument("--batch-id", required=True)
    export_evolution.add_argument("--deliverer", default="zhigou-ontology")
    check_input = sub.add_parser("inspect-input")
    check_input.add_argument("directory", type=Path)
    generation = sub.add_parser("export-generation")
    generation.add_argument("directory", type=Path)
    generation.add_argument("output", type=Path)
    cover = sub.add_parser("assemble-handoff")
    cover.add_argument("output", type=Path)
    cover.add_argument("--downstream", type=Path)
    cover.add_argument("--evolution", type=Path)
    cover.add_argument("--diagnostic", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "inspect":
        result = V3Delivery(read_zip(args.archive.read_bytes())).inspect(run_shacl=args.shacl)
    elif args.command == "preflight-native":
        result = inspect_native(args.archive)
    elif args.command == "export-diagnostic":
        data = diagnostic_bytes(args.archive)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            stream.write(data)
        result = {"status": "DIAGNOSTIC_EXPORTED", "v3_export_created": False, "release_status": "NOT_RELEASED"}
    elif args.command == "export-handoff":
        from zhigou_toolchain.environment import get_setting
        from zhigou_toolchain.service_runtime.configuration import load_configuration
        from zhigou_toolchain.services.facade import ApplicationService
        from zhigou_toolchain.services.handoff import download
        app = ApplicationService(load_configuration(args.workspace))
        principal = app.authenticate("Bearer " + get_setting("TOKEN", ""))
        raw = download(app, principal, args.project_id, args.job_id)
        atomic_file(args.output, raw)
        result = {"status": "EXPORTED", "source": "AUTHORIZED_COMMITTED_SERVICE_SNAPSHOT"}
    elif args.command == "validate-handoff":
        from .handoff import verify_handoff
        result = verify_handoff(read_zip(read_bounded(args.archive)), trusted_receipt=json.loads(read_bounded(args.receipt)) if args.receipt else None)
    elif args.command == "validate-stage":
        from .stage import verify_stage_archive
        result = verify_stage_archive(args.archive, expected_sha256=args.sha256, replay_negatives=args.replay_negatives)
    elif args.command == "validate-evolution":
        from .evolution import validate_batch
        result = validate_batch(read_directory(args.directory), producer=args.producer)
    elif args.command == "export-evolution":
        from .evolution import evolution_files, export_batch
        traces = [json.loads(read_bounded(path)) for path in args.trace]
        result = export_batch(args.output, evolution_files(traces, batch_id=args.batch_id, deliverer=args.deliverer))
    elif args.command == "assemble-handoff":
        from .cover import compose, verify_cover
        files = compose(downstream=read_zip(read_bounded(args.downstream)) if args.downstream else None,
            evolution=read_directory(args.evolution) if args.evolution else None,
            diagnostic=read_directory(args.diagnostic) if args.diagnostic else None)
        result = verify_cover(files)
        write_directory(args.output, files, manifest="handoff_manifest.json")
    else:
        from .meeting_input import generation_files, validate_input
        files = read_directory(args.directory)
        parsed = validate_input(files)
        if args.command == "export-generation":
            write_directory(args.output, generation_files(files), manifest="manifest.json")
        result = {"status": "GENERATION_VIEW_EXPORTED" if args.command == "export-generation" else "VALIDATED_INPUT_EXCHANGE",
                  "package_id": parsed["manifest"]["package_id"], "native_ingestion": "NOT_PERFORMED_BY_INSPECTION"}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        atomic_file(args.report, json_bytes(result))
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get("status") == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
