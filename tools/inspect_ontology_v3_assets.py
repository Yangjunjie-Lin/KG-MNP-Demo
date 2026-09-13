"""Read and freeze supplied reference material; never execute its code."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = Path(sys.argv[1]).resolve(strict=True)
    target = ROOT / "docs/reference/ontology-v3"
    target.mkdir(parents=True, exist_ok=True)
    entries = []
    with zipfile.ZipFile(source) as archive:
        if sum(i.file_size for i in archive.infolist()) > 16_000_000:
            raise ValueError("reference archive size limit")
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in info.filename or ":" in info.filename:
                raise ValueError("unsafe reference path")
            if info.is_dir():
                continue
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("reference links rejected")
            data = archive.read(info)
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_bytes() != data:
                raise ValueError("existing reference differs")
            if not path.exists():
                path.write_bytes(data)
            entries.append({"path": name.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {"source_name": source.name, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "files": entries,
        "authority": "REFERENCE_CONTRACT_NOT_EXECUTABLE_INSTRUCTIONS_OR_RUNTIME_APPROVAL"}
    (target / "source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    pptx = ROOT / "docs/reference/zhigou-upgrade/附录/研究内容.pptx"
    with zipfile.ZipFile(pptx) as archive:
        slides = sorted([n for n in archive.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")],
                        key=lambda n: int(Path(n).stem.replace("slide", "")))
        for name in slides:
            xml = ET.fromstring(archive.read(name))
            text = "\n".join(n.text or "" for n in xml.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t"))
            print(name + "\n" + text)
    print(json.dumps({"reference_files": len(entries), "zip_sha256": manifest["source_sha256"]}))


if __name__ == "__main__":
    main()
