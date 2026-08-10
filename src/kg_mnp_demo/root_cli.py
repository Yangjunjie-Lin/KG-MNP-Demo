"""Route the top-level command without extending frozen Foundation CLIs."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Route Application commands and preserve every Foundation argument verbatim."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "application":
        from .application.cli import main as application_main

        return application_main(arguments[1:])

    from .modeling.cli import main as modeling_main

    return modeling_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
