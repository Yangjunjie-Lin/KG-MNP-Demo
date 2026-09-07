"""Mechanically redact authentication headers in owned browser-test evidence.

Preserves failure status, assertion and locations. Does not touch credentials,
source data, screenshots, repositories or arbitrary user directories.
"""
import argparse
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    base = (Path(__file__).resolve().parents[1] / "runtime_logs/p09/browser-runs").resolve()
    target = args.run_directory.resolve(strict=True)
    if target != base and not target.is_relative_to(base):
        raise SystemExit("only owned browser evidence directories are accepted")
    changed = []
    for path in target.rglob("*"):
        if path.is_symlink() or path.suffix not in {".xml", ".json", ".md", ".log", ".txt"}:
            continue
        source = path.read_text(encoding="utf-8")
        result = re.sub(r"(?im)(^.*\b(?:cookie|authorization|x-csrf-token):)[^\r\n]*", r"\1 [REDACTED]", source)
        result = re.sub(r"kgmnp_session=[^\s;\"']+", "kgmnp_session=[REDACTED]", result)
        if result != source:
            path.write_text(result, encoding="utf-8")
            changed.append(path.relative_to(base).as_posix())
    print(f"Redacted authentication headers in {len(changed)} owned evidence files; failures retained")


if __name__ == "__main__":
    main()
