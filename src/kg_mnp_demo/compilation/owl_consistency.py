"""Package-level OWL 2 DL consistency check using the Stage 03 ROBOT/HermiT pin."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Mapping

import yaml
from rdflib import OWL, Graph

from ..modeling.dependencies import ROOT
from .rdf_canonical import canonical_ntriples

ROBOT_VERSION = "1.9.7"
ROBOT_SHA256 = "91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d"
ROBOT_JAR = ROOT / "third_party" / "downloads" / f"robot-{ROBOT_VERSION}.jar"
HERMIT_POM = "META-INF/maven/net.sourceforge.owlapi/org.semanticweb.hermit/pom.properties"


class OWLConsistencyError(ValueError):
    pass


def load_ontology_graph(*, root: Path = ROOT) -> Graph:
    config = yaml.safe_load((root / "config" / "ontology_modules.yaml").read_text(encoding="utf-8"))
    graph = Graph()
    graph.parse(root / "ontology" / config["root"]["file"], format="turtle")
    for entry in config["modules"]:
        if entry.get("runtime") is True:
            graph.parse(root / "ontology" / entry["file"], format="turtle")
    for triple in list(graph.triples((None, OWL.imports, None))):
        graph.remove(triple)
    return graph


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hermit_version(jar: Path) -> str:
    try:
        with zipfile.ZipFile(jar) as archive:
            text = archive.read(HERMIT_POM).decode("iso-8859-1")
    except (OSError, KeyError, zipfile.BadZipFile):
        return "UNKNOWN"
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "version":
            return value.strip()
    return "UNKNOWN"


def check_owl_consistency(
    abox_graph: Graph,
    ontology_baseline: Mapping[str, Any],
    source_package_hash: str,
    *,
    ontology_graph: Graph | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    root = root.resolve()
    asserted_ontology = ontology_graph if ontology_graph is not None else load_ontology_graph(root=root)
    abox_semantic_hash = hashlib.sha256(canonical_ntriples(abox_graph)).hexdigest()
    combined = Graph()
    for graph in (asserted_ontology, abox_graph):
        for triple in graph:
            if triple[1] != OWL.imports:
                combined.add(triple)
    combined_bytes = canonical_ntriples(combined)
    combined_hash = hashlib.sha256(combined_bytes).hexdigest()
    base = {
        "reasoner": "HermiT",
        "robot_version": ROBOT_VERSION,
        "robot_jar_sha256": ROBOT_SHA256,
        "hermit_dependency_version": "UNKNOWN",
        "ontology_release_source_hash": str(ontology_baseline.get("release_source_hash")),
        "abox_semantic_hash": abox_semantic_hash,
        "combined_input_semantic_hash": combined_hash,
        "source_package_hash": source_package_hash,
    }
    robot_jar = root / "third_party" / "downloads" / ROBOT_JAR.name
    if not robot_jar.is_file() or _sha256(robot_jar) != ROBOT_SHA256:
        return {**base, "status": "FAILED", "consistent": False, "exit_code": None}
    base["hermit_dependency_version"] = _hermit_version(robot_jar)
    work = root / "runtime_outputs" / "compilation" / f".reasoner-{combined_hash}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    input_path = work / "combined.nt"
    output_path = work / "reasoned.owl"
    input_path.write_bytes(combined_bytes)
    try:
        process = subprocess.run(
            [
                "java", "-jar", str(robot_jar), "reason",
                "--input", str(input_path), "--reasoner", "hermit",
                "--equivalent-classes-allowed", "all", "--output", str(output_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=180,
        )
        output = "\n".join((process.stdout, process.stderr))
        if process.returncode == 0 and output_path.is_file():
            status = "CONSISTENT"
        elif re.search(r"ontology\s+is\s+inconsistent|inconsistent\s+ontology|inconsistency", output, re.I):
            status = "INCONSISTENT"
        else:
            status = "FAILED"
        return {
            **base,
            "status": status,
            "consistent": status == "CONSISTENT",
            "exit_code": process.returncode,
        }
    except (OSError, subprocess.SubprocessError):
        return {**base, "status": "FAILED", "consistent": False, "exit_code": None}
    finally:
        shutil.rmtree(work, ignore_errors=True)
