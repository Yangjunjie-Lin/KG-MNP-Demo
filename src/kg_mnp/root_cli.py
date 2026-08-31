"""Route the top-level command without extending frozen Foundation CLIs."""

from __future__ import annotations

import sys

_ROOT_HELP = """usage: kg-mnp <command> [options]

KG-MNP Ontology Toolchain - Evidence-Bound Ingestion Kernel

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
  application   governed application workflow
  workbench     read-only workbench
  diagnostics   diagnostics workflow
  governance    governance workflow
  amendment     amendment workflow
  activation    activation and rollback

Run `kg-mnp <command> --help` for command-specific help.
"""


def main(argv: list[str] | None = None) -> int:
    """Route Application commands and preserve every Foundation argument verbatim."""

    arguments = list(sys.argv[1:] if argv is None else argv)
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
    if arguments and arguments[0] == "application":
        from .application.cli import main as application_main

        return application_main(arguments[1:])

    if arguments and arguments[0] == "workbench":
        from .workbench.cli import main as workbench_main

        return workbench_main(arguments[1:])

    if arguments and arguments[0] == "diagnostics":
        from .diagnostics.cli import main as diagnostics_main

        return diagnostics_main(arguments[1:])

    if arguments and arguments[0] == "governance":
        from .governance.cli import main as governance_main

        return governance_main(arguments[1:])

    if arguments and arguments[0] == "amendment":
        from .amendment.cli import main as amendment_main

        return amendment_main(arguments[1:])

    if arguments and arguments[0] == "activation":
        from .activation.cli import main as activation_main

        return activation_main(arguments[1:])

    from .modeling.cli import main as modeling_main

    return modeling_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
