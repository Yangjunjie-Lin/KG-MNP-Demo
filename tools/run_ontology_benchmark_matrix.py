"""Thin entry point; all task logic stays in ontology_io."""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        from zhigou_toolchain.ontology_io.live_runner import main
        main(sys.argv[2:])
    else:
        from zhigou_toolchain.ontology_io.matrix import main
        raise SystemExit(main())
