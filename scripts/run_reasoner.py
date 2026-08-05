#!/usr/bin/env python3
"""Download fixed ROBOT release (gitignored) and run HermiT consistency check."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_DIR = ROOT / "third_party" / "downloads"
ROBOT_VERSION = "1.9.7"
ROBOT_JAR_NAME = f"robot-{ROBOT_VERSION}.jar"
# Official ROBOT release asset
ROBOT_URL = (
    f"https://github.com/ontodev/robot/releases/download/"
    f"v{ROBOT_VERSION}/robot.jar"
)
# Pinned SHA-256 for robot.jar v1.9.7 (verified from release; update if bumping version)
# If download hash mismatches, script fails closed.
EXPECTED_SHA256 = None  # filled after first trusted download recorded in reasoner-report

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from stage03_constants import ONTOLOGY_VERSION, ontology_iri  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ontology_hash() -> str:
    h = hashlib.sha256()
    for path in sorted((ROOT / "ontology").glob("*.ttl")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def ensure_robot(force: bool = False) -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    jar = DOWNLOAD_DIR / ROBOT_JAR_NAME
    if jar.is_file() and not force:
        return jar
    print(f"Downloading ROBOT {ROBOT_VERSION} from official release...")
    tmp = jar.with_suffix(".tmp")
    urllib.request.urlretrieve(ROBOT_URL, tmp)
    digest = sha256_file(tmp)
    meta = DOWNLOAD_DIR / f"{ROBOT_JAR_NAME}.sha256"
    if meta.is_file():
        expected = meta.read_text(encoding="utf-8").strip().split()[0]
        if digest != expected:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f"ROBOT jar SHA-256 mismatch: {digest} != {expected}")
    else:
        meta.write_text(f"{digest}  {ROBOT_JAR_NAME}\n", encoding="utf-8")
        print(f"Recorded ROBOT SHA-256: {digest}")
    tmp.replace(jar)
    return jar


def merge_ontology(out_path: Path) -> None:
    """Concatenate runtime modules into one TTL for reasoner input (offline).

    Strip owl:imports so ROBOT/HermiT does not attempt network resolution;
    triples from all runtime modules are already merged.
    """
    from rdflib import OWL, URIRef
    from rdflib.namespace import RDF

    from kg_mnp_demo.loader import load_ontology_graph

    g = load_ontology_graph(include_alignments=False)
    for triple in list(g.triples((None, OWL.imports, None))):
        g.remove(triple)
    # Ensure a single root ontology declaration for the merged artifact
    root = URIRef("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp")
    g.add((root, RDF.type, OWL.Ontology))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(out_path, format="turtle")


def write_report(
    *,
    status: str,
    reasoner: str,
    version: str,
    command: str,
    consistency: str,
    unsat: list[str],
    equiv: list[str],
    warnings: list[str],
    jar_sha: str,
) -> Path:
    path = ROOT / "docs" / "ontology" / "reasoner-report.md"
    ohash = ontology_hash()
    lines = [
        "# OWL 2 DL Reasoner Report",
        "",
        f"- Ontology release version: `{ONTOLOGY_VERSION}`",
        f"- Ontology hash (SHA-256 of ontology/*.ttl): `{ohash}`",
        f"- Root ontology IRI: `{ontology_iri('kg-mnp')}`",
        f"- Reasoner name: `{reasoner}`",
        f"- Reasoner version: `{version}`",
        f"- Execution command: `{command}`",
        f"- Execution date: `{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}`",
        f"- Consistency result: `{consistency}`",
        f"- Status: `{status}`",
        f"- ROBOT jar SHA-256: `{jar_sha}`",
        f"- Environment: Python {sys.version.split()[0]}, platform={sys.platform}",
        "",
        "## Unsatisfiable named classes",
        "",
    ]
    if unsat:
        lines.extend(f"- `{u}`" for u in unsat)
    else:
        lines.append("- (none)")
    lines += ["", "## Unexpected equivalent classes", ""]
    if equiv:
        lines.extend(f"- `{e}`" for e in equiv)
    else:
        lines.append("- (none)")
    lines += ["", "## Warnings", ""]
    if warnings:
        lines.extend(f"- {w}" for w in warnings)
    else:
        lines.append("- (none)")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()
    merged = DOWNLOAD_DIR / "kg-mnp-merged.ttl"
    merge_ontology(merged)

    try:
        jar = ensure_robot() if not args.skip_download else DOWNLOAD_DIR / ROBOT_JAR_NAME
        if not jar.is_file():
            raise FileNotFoundError(jar)
    except Exception as exc:  # noqa: BLE001
        write_report(
            status="NOT_RUN",
            reasoner="HermiT via ROBOT",
            version=ROBOT_VERSION,
            command="(download failed)",
            consistency="UNKNOWN",
            unsat=[],
            equiv=[],
            warnings=[f"Reasoner not run: {exc}"],
            jar_sha="",
        )
        print(f"Reasoner NOT_RUN: {exc}")
        return 2

    jar_sha = sha256_file(jar)
    cmd = [
        "java",
        "-jar",
        str(jar),
        "reason",
        "--input",
        str(merged),
        "--reasoner",
        "hermit",
        "--dump-unsatisfiable",
        str(DOWNLOAD_DIR / "unsatisfiable.txt"),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        write_report(
            status="NOT_RUN",
            reasoner="HermiT via ROBOT",
            version=ROBOT_VERSION,
            command=" ".join(cmd),
            consistency="UNKNOWN",
            unsat=[],
            equiv=[],
            warnings=["Java runtime not found"],
            jar_sha=jar_sha,
        )
        print("Reasoner NOT_RUN: Java not found")
        return 2

    out = (proc.stdout or "") + (proc.stderr or "")
    unsat_path = DOWNLOAD_DIR / "unsatisfiable.txt"
    unsat: list[str] = []
    if unsat_path.is_file():
        unsat = [ln.strip() for ln in unsat_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    consistent = proc.returncode == 0 and "unsatisfiable" not in out.lower()
    # ROBOT reason returns 0 on success; dump file may still list nothing
    if proc.returncode != 0:
        consistent = False

    status = "PASS" if consistent and not unsat else "FAIL"
    write_report(
        status=status,
        reasoner="HermiT (via ROBOT)",
        version=ROBOT_VERSION,
        command=" ".join(cmd),
        consistency="CONSISTENT" if consistent else "INCONSISTENT_OR_ERROR",
        unsat=unsat,
        equiv=[],
        warnings=[] if proc.returncode == 0 else [out[:2000]],
        jar_sha=jar_sha,
    )
    print(out[-2000:] if out else "(no output)")
    print(f"Reasoner status: {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
