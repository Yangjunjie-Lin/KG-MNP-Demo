"""Current product entry points; obsolete runtime platforms are retired."""

from __future__ import annotations

import sys

_ROOT_HELP = """usage: kg-mnp <command> [options]

KG-MNP Ontology Toolchain

commands:
  contracts     public contract catalog and validation
  domain-pack   local domain pack registry
  workspace     project workspace lifecycle
  plugin        Plugin SDK registry, snapshots, and conformance
  source        content-addressed source registration
  ingest        deterministic planning and transactional execution
  ir            evidence-bound KG-IR inspection and trace
  model         evidence-grounded ontology modeling proposals
  review        explicit human review and confirmation
  compile       deterministic semantic compilation and validation
  package       VALIDATED_UNPUBLISHED ontology package verification/export
  lifecycle     ontology registry, semantic diff, regression, release, and environment lifecycle
  service       unified application service, credentials, API, and jobs

Run `kg-mnp <command> --help` for command-specific help.
"""


def main(argv: list[str] | None = None) -> int:
    """Route current commands; reject retired entry points before loading them."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in {"application","workbench","diagnostics","governance","amendment","activation",
        "evaluate","trace","validate","infer","mappings","sources","run-all","propose","confirm","graphdb","publication","webvowl"}:
        print("CLI_RETIRED: use kg-mnp service serve and authenticated model/review/lifecycle resources")
        return 2
    if arguments in ([], ["-h"], ["--help"]):
        print(_ROOT_HELP, end="")
        return 0
    if arguments and arguments[0] == "contracts":
        from .contracts.cli import main as contracts_main

        return contracts_main(arguments[1:])

    if arguments and arguments[0] == "domain-pack":
        from .domain_packs.cli import main as domain_pack_main

        return domain_pack_main(arguments[1:])

    if arguments and arguments[0] == "workspace":
        from .workspace.cli import main as workspace_main

        return workspace_main(arguments[1:])

    if arguments and arguments[0] == "plugin":
        from .plugins.cli import main as plugin_main

        return plugin_main(arguments[1:])

    if arguments and arguments[0] == "source":
        from .ingestion.cli import source_main

        return source_main(arguments[1:])

    if arguments and arguments[0] == "ingest":
        from .ingestion.cli import ingest_main

        return ingest_main(arguments[1:])

    if arguments and arguments[0] == "ir":
        from .ingestion.cli import ir_main

        return ir_main(arguments[1:])
    if arguments and arguments[0] == "model":
        from .modeling.control_plane.cli import main as model_main

        return model_main(arguments[1:])

    if arguments and arguments[0] == "review":
        from .modeling.control_plane.review.cli import main as review_main

        return review_main(arguments[1:])

    if arguments and arguments[0] == "compile":
        from .semantic_kernel.cli import compile_main

        return compile_main(arguments[1:])

    if arguments and arguments[0] == "package":
        from .semantic_kernel.cli import package_main

        return package_main(arguments[1:])
    if arguments and arguments[0] == "lifecycle":
        from .lifecycle.cli import main as lifecycle_main

        return lifecycle_main(arguments[1:])

    if arguments and arguments[0] == "service":
        from .services.cli import main as service_main

        return service_main(arguments[1:])

    print("Unknown command; use kg-mnp --help", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
