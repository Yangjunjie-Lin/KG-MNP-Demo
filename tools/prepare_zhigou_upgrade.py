"""Preserve the starting increment and inspect supplied reference bytes."""
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = root / "runtime_reports" / f"upgrade-recovery-{stamp}"
    target.mkdir(parents=True)
    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=root)
    paths = set(git("diff", "--name-only", "-z").decode().split("\0"))
    paths.update(git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"))
    manifest = {}
    with zipfile.ZipFile(target / "starting-increment.zip", "w", zipfile.ZIP_DEFLATED) as backup:
        for name in sorted(paths - {""}):
            path = root / name
            if path.is_file():
                content = path.read_bytes()
                backup.writestr(name, content)
                manifest[name] = hashlib.sha256(content).hexdigest()
    (target / "working-tree.patch").write_bytes(git("diff", "--binary"))
    (target / "staged.patch").write_bytes(git("diff", "--cached", "--binary"))
    (target / "inventory.json").write_text(json.dumps({"head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("branch", "--show-current").decode().strip(), "files": manifest}, indent=2), encoding="utf-8")
    reference = root / "docs" / "reference" / "zhigou-upgrade"
    reference.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive) as archive:
        for item in archive.infolist():
            destination = (reference / item.filename).resolve()
            if not destination.is_relative_to(reference.resolve()) or item.is_dir():
                raise ValueError("Unexpected archive member")
            content = archive.read(item)
            if destination.exists() and destination.read_bytes() != content:
                raise ValueError("Reference already exists with different content")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    with zipfile.ZipFile(reference / "附录" / "研究内容.pptx") as presentation:
        for name in sorted(presentation.namelist()):
            if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                tree = ElementTree.fromstring(presentation.read(name))
                print(name, "\n", "\n".join(node.text or "" for node in tree.iter() if node.tag.endswith("}t")))
    print(json.dumps({"recovery": str(target), "references": str(reference), "preserved_files": len(manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
