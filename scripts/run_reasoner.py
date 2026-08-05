#!/usr/bin/env python3
"""Run the pinned ROBOT/HermiT Stage 03 gate without changing tracked files.

The default command writes only ignored runtime artifacts. A successful runtime
result can be promoted explicitly to the tracked JSON attestation and its
deterministically rendered Markdown view with ``--update-attestation``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import itertools
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml
from rdflib import OWL, RDF, RDFS, Graph, URIRef
from rdflib.compare import to_canonical_graph

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_DIR = ROOT / "third_party" / "downloads"
RUNTIME_DIR = ROOT / "runtime_reports" / "ontology"
RUNTIME_REPORT_PATH = RUNTIME_DIR / "reasoner-run.json"
REASONER_INPUT_PATH = RUNTIME_DIR / "reasoner-input.nt"
REASONED_ONTOLOGY_PATH = RUNTIME_DIR / "reasoned-ontology.owl"
UNSAT_DEBUG_PATH = RUNTIME_DIR / "unsatisfiable-debug.owl"
UNSAT_REPORT_PATH = RUNTIME_DIR / "unsatisfiable.txt"
EQUIVALENCE_REPORT_PATH = RUNTIME_DIR / "unexpected-equivalences.json"
ATTESTATION_PATH = ROOT / "docs" / "ontology" / "reasoner-attestation.json"
MARKDOWN_REPORT_PATH = ROOT / "docs" / "ontology" / "reasoner-report.md"
ALLOWLIST_PATH = ROOT / "config" / "reasoner-allowlist.yaml"

ROBOT_VERSION = "1.9.7"
EXPECTED_RDFLIB_VERSION = "7.6.0"
EXPECTED_ROBOT_SHA256 = (
    "91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d"
)
ROBOT_JAR_NAME = f"robot-{ROBOT_VERSION}.jar"
ROBOT_URL = (
    "https://github.com/ontodev/robot/releases/download/v1.9.7/robot.jar"
)
HERMIT_POM_PROPERTIES = (
    "META-INF/maven/net.sourceforge.owlapi/"
    "org.semanticweb.hermit/pom.properties"
)
ROBOT_POM_PROPERTIES = (
    "META-INF/maven/org.obolibrary.robot/robot-command/pom.properties"
)

TERM_NAMESPACE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"
ROOT_ONTOLOGY_IRI = (
    "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp"
)
PORTABLE_EXECUTION_COMMAND = "python scripts/run_reasoner.py"
PORTABLE_ROBOT_COMMAND = (
    "java -jar <ROBOT_JAR> reason --input <REASONER_INPUT> "
    "--reasoner hermit --equivalent-classes-allowed all "
    '--axiom-generators "SubClass EquivalentClass" '
    "--dump-unsatisfiable <UNSAT_DEBUG_ONTOLOGY> "
    "--output <REASONED_ONTOLOGY>"
)

STATUS_PASS = "PASS"
STATUS_FAIL_INCONSISTENT = "FAIL_INCONSISTENT"
STATUS_FAIL_UNSATISFIABLE_CLASSES = "FAIL_UNSATISFIABLE_CLASSES"
STATUS_FAIL_UNEXPECTED_EQUIVALENCES = "FAIL_UNEXPECTED_EQUIVALENCES"
STATUS_FAIL_TOOL_ERROR = "FAIL_TOOL_ERROR"
STATUS_NOT_RUN = "NOT_RUN"

CONSISTENT = "CONSISTENT"
INCONSISTENT = "INCONSISTENT"
UNKNOWN = "UNKNOWN"

_INCONSISTENCY_PATTERNS = (
    re.compile(r"\bontology\s+is\s+inconsistent\b", re.IGNORECASE),
    re.compile(r"\binconsistent\s+ontology\b", re.IGNORECASE),
    re.compile(r"\binconsistency\s+detected\b", re.IGNORECASE),
)

_PORTABILITY_PATTERNS = (
    ("Windows drive path", re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")),
    ("Windows UNC path", re.compile(r"\\\\[^\\\s]+\\")),
    ("Linux home path", re.compile(r"/home/[^/\s]+(?:/|$)")),
    ("macOS home path", re.compile(r"/Users/[^/\s]+(?:/|$)")),
    (
        "POSIX project checkout path",
        re.compile(r"(?<![A-Za-z0-9:/])/(?!/)[^\r\n`]*KG-MNP-Demo(?:/|$)"),
    ),
)


class RobotChecksumError(RuntimeError):
    """The ROBOT cache or download did not match the pinned checksum."""


class UnsatisfiableReportError(RuntimeError):
    """A normalized unsatisfiable-class report could not be read safely."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text_bytes(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    payload = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    _write_text_bytes(path, payload + "\n")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def ensure_robot(*, download_dir: Path | None = None) -> Path:
    """Return a checksum-verified ROBOT JAR from the fixed official URL.

    Existing caches are always hashed. Downloads are first written to a
    temporary file and promoted only after matching the hard-coded SHA-256.
    Local ``.sha256`` files are neither read nor written as trust material.
    """

    target_dir = download_dir if download_dir is not None else DOWNLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    jar = target_dir / ROBOT_JAR_NAME

    if jar.is_file():
        actual = sha256_file(jar)
        if actual != EXPECTED_ROBOT_SHA256:
            # Never leave an invalid file at the canonical cache path.
            jar.unlink(missing_ok=True)
            raise RobotChecksumError(
                "cached ROBOT JAR SHA-256 mismatch: "
                f"expected {EXPECTED_ROBOT_SHA256}, got {actual}"
            )
        return jar

    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{ROBOT_JAR_NAME}.",
        suffix=".tmp",
        dir=target_dir,
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        print(f"Downloading ROBOT {ROBOT_VERSION} from {ROBOT_URL}")
        urllib.request.urlretrieve(ROBOT_URL, temporary)
        actual = sha256_file(temporary)
        if actual != EXPECTED_ROBOT_SHA256:
            raise RobotChecksumError(
                "downloaded ROBOT JAR SHA-256 mismatch: "
                f"expected {EXPECTED_ROBOT_SHA256}, got {actual}"
            )
        temporary.replace(jar)
    finally:
        temporary.unlink(missing_ok=True)

    return jar


def _maven_version_from_jar(jar: Path, member: str) -> str:
    try:
        with zipfile.ZipFile(jar) as archive:
            text = archive.read(member).decode("iso-8859-1")
    except (KeyError, OSError, UnicodeError, zipfile.BadZipFile):
        return UNKNOWN
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "version" and value.strip():
            return value.strip()
    return UNKNOWN


def hermit_version_from_robot(jar: Path) -> str:
    """Read HermiT's own Maven version from the checksum-pinned fat JAR."""

    return _maven_version_from_jar(jar, HERMIT_POM_PROPERTIES)


def robot_embedded_version(jar: Path) -> str:
    return _maven_version_from_jar(jar, ROBOT_POM_PROPERTIES)


def java_version() -> str:
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return UNKNOWN
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    match = re.search(r'(?:java|openjdk)\s+version\s+"([^"]+)"', output)
    if match:
        return match.group(1)
    match = re.search(r"\bopenjdk\s+([^\s]+)", output)
    return match.group(1) if match else UNKNOWN


def java_major_version(version: str) -> int | None:
    match = re.match(r"^(?:1\.)?(\d+)", version)
    return int(match.group(1)) if match else None


def installed_rdflib_version() -> str:
    try:
        return importlib.metadata.version("rdflib")
    except importlib.metadata.PackageNotFoundError:
        return UNKNOWN


def _load_module_config(root: Path = ROOT) -> dict[str, Any]:
    path = root / "config" / "ontology_modules.yaml"
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("modules"), list):
        raise ValueError(f"Invalid ontology module configuration: {path}")
    return value


def ontology_version(root: Path = ROOT) -> str:
    value = _load_module_config(root).get("ontology_version")
    if not isinstance(value, str) or not value:
        raise ValueError("config/ontology_modules.yaml has no ontology_version")
    return value


def release_source_files(
    root: Path = ROOT,
    *,
    include_alignments: bool = False,
) -> list[Path]:
    """Files covered by the release-source hash.

    The default profile includes the root ontology, all runtime module TTL,
    the module configuration, and the catalog. The optional alignment TTL is
    included only when ``include_alignments`` is true. Its descriptor entries
    remain visible in the configuration/catalog governance files in both
    profiles, but its RDF source bytes are excluded from the default profile.
    """

    config = _load_module_config(root)
    relative_paths = {
        Path("config/ontology_modules.yaml"),
    }
    root_config = config.get("root")
    if not isinstance(root_config, dict):
        raise ValueError("ontology module configuration has no root object")
    root_file = root_config.get("file")
    catalog = root_config.get("catalog")
    if not isinstance(root_file, str) or not isinstance(catalog, str):
        raise ValueError("ontology root file/catalog entries are invalid")
    relative_paths.add(Path("ontology") / root_file)
    relative_paths.add(Path("ontology") / catalog)

    for entry in config["modules"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            raise ValueError("invalid ontology module entry")
        if bool(entry.get("runtime")) or (
            include_alignments and bool(entry.get("optional"))
        ):
            relative_paths.add(Path("ontology") / entry["file"])

    files = [root / path for path in sorted(relative_paths, key=lambda p: p.as_posix())]
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing release source file: {missing[0]}")
    return files


def _normalized_source_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def ontology_release_source_hash(
    root: Path = ROOT,
    *,
    include_alignments: bool = False,
) -> str:
    digest = hashlib.sha256()
    digest.update(b"KG-MNP ontology release source hash v1\0")
    for path in release_source_files(root, include_alignments=include_alignments):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = _normalized_source_bytes(path)
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(len(content)).encode("ascii"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def asserted_reasoner_graph(root: Path = ROOT) -> Graph:
    """Load the root and runtime modules, excluding optional alignments."""

    config = _load_module_config(root)
    graph = Graph()
    root_config = config["root"]
    graph.parse(root / "ontology" / root_config["file"], format="turtle")
    for entry in config["modules"]:
        if bool(entry.get("runtime")):
            graph.parse(root / "ontology" / entry["file"], format="turtle")
    for triple in list(graph.triples((None, OWL.imports, None))):
        graph.remove(triple)
    graph.add((URIRef(root_config["ontology_iri"]), RDF.type, OWL.Ontology))
    return graph


def canonical_graph_bytes(graph: Graph) -> bytes:
    """Return deterministic, sorted canonical N-Triples for an RDF graph."""

    canonical = to_canonical_graph(graph)
    serialized = canonical.serialize(format="nt")
    if isinstance(serialized, bytes):
        text = serialized.decode("utf-8")
    else:
        text = serialized
    lines = sorted(line.strip() for line in text.splitlines() if line.strip())
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def reasoner_input_semantic_hash(graph: Graph) -> str:
    return sha256_bytes(canonical_graph_bytes(graph))


def write_reasoner_input(
    out_path: Path = REASONER_INPUT_PATH,
    *,
    root: Path = ROOT,
) -> tuple[Graph, str, str]:
    graph = asserted_reasoner_graph(root)
    canonical = canonical_graph_bytes(graph)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(canonical)
    semantic_hash = sha256_bytes(canonical)
    return graph, semantic_hash, sha256_file(out_path)


def _normalize_named_class(value: str) -> str | None:
    value = value.strip().strip("<>[](),;.")
    if value in {
        "owl:Nothing",
        "Nothing",
        str(OWL.Nothing),
    }:
        return None
    if value.startswith("mnp:") and len(value) > 4:
        return TERM_NAMESPACE + value[4:]
    if value.startswith("owl:"):
        return str(OWL[value[4:]])
    return value or None


def find_unsatisfiable_named_classes(graph: Graph) -> list[str]:
    """Find named classes inferred equivalent/subclassed to owl:Nothing."""

    found: set[str] = set()
    nothing = OWL.Nothing
    for subject, obj in graph.subject_objects(OWL.equivalentClass):
        if subject == nothing and isinstance(obj, URIRef) and obj != nothing:
            found.add(str(obj))
        if obj == nothing and isinstance(subject, URIRef) and subject != nothing:
            found.add(str(subject))
    for subject in graph.subjects(RDFS.subClassOf, nothing):
        if isinstance(subject, URIRef) and subject != nothing:
            found.add(str(subject))
    return sorted(found)


def parse_unsatisfiable_file(path: Path) -> list[str]:
    """Parse the normalized text report, including URI and CURIE forms.

    Missing files and invalid UTF-8 are errors. Empty files, comments/headers,
    and ``owl:Nothing`` alone mean that no named unsatisfiable class was
    reported.
    """

    if not path.is_file():
        raise UnsatisfiableReportError(f"unsatisfiable report is missing: {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise UnsatisfiableReportError(
            f"unsatisfiable report is not valid UTF-8: {path}"
        ) from exc
    if not text.strip():
        return []

    found: set[str] = set()
    iri_pattern = re.compile(r"<([^>]+)>|(https?://[^\s,;]+)")
    curie_pattern = re.compile(r"\b([A-Za-z][\w.-]*:[A-Za-z_][\w.-]*)\b")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "//", ";", "|")):
            continue
        for match in iri_pattern.finditer(line):
            normalized = _normalize_named_class(match.group(1) or match.group(2))
            if normalized is not None:
                found.add(normalized)
        for match in curie_pattern.finditer(line):
            value = match.group(1)
            if value.startswith(("http:", "https:")):
                continue
            prefix = value.split(":", 1)[0].lower()
            if prefix in {"status", "result", "encoding", "header"}:
                continue
            normalized = _normalize_named_class(value)
            if normalized is not None:
                found.add(normalized)
    return sorted(found)


def write_unsatisfiable_report(path: Path, classes: Sequence[str]) -> None:
    lines = [
        "# Unsatisfiable named classes derived from the HermiT reasoned graph.",
    ]
    if classes:
        lines.extend(f"<{value}>" for value in sorted(set(classes)))
    else:
        lines.append("# none")
    _write_text_bytes(path, "\n".join(lines) + "\n")


def _equivalence_pairs(graph: Graph) -> set[tuple[str, str]]:
    adjacency: dict[str, set[str]] = {}
    for left, right in graph.subject_objects(OWL.equivalentClass):
        if not isinstance(left, URIRef) or not isinstance(right, URIRef):
            continue
        if left == right or OWL.Nothing in {left, right}:
            continue
        left_text, right_text = str(left), str(right)
        adjacency.setdefault(left_text, set()).add(right_text)
        adjacency.setdefault(right_text, set()).add(left_text)

    pairs: set[tuple[str, str]] = set()
    visited: set[str] = set()
    for start in sorted(adjacency):
        if start in visited:
            continue
        component: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency.get(current, ()))
        visited.update(component)
        pairs.update(itertools.combinations(sorted(component), 2))
    return pairs


def _normalize_equivalence_pair(value: Any) -> tuple[str, str]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("each expected_equivalent_classes entry must have two IRIs")
    if not all(isinstance(item, str) and item.startswith(("http://", "https://")) for item in value):
        raise ValueError("equivalent-class allowlist values must be absolute IRIs")
    left, right = sorted(value)
    if left == right:
        raise ValueError("equivalent-class allowlist cannot contain self pairs")
    if str(OWL.Nothing) in {left, right}:
        raise ValueError("owl:Nothing belongs in the unsatisfiable-class check")
    return left, right


def load_equivalence_allowlist(path: Path = ALLOWLIST_PATH) -> set[tuple[str, str]]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Invalid reasoner allowlist: {path}")
    entries = value.get("expected_equivalent_classes", [])
    if not isinstance(entries, list):
        raise ValueError("expected_equivalent_classes must be a list")
    return {_normalize_equivalence_pair(entry) for entry in entries}


def detect_inferred_equivalent_classes(
    asserted: Graph,
    reasoned: Graph,
    allowlist: Iterable[tuple[str, str]] = (),
) -> tuple[list[list[str]], list[list[str]], list[list[str]]]:
    """Return all inferred, approved inferred, and unexpected pairs."""

    inferred = _equivalence_pairs(reasoned) - _equivalence_pairs(asserted)
    allowed_pairs = set(allowlist)
    approved = inferred & allowed_pairs
    unexpected = inferred - allowed_pairs
    def as_lists(pairs: set[tuple[str, str]]) -> list[list[str]]:
        return [list(pair) for pair in sorted(pairs)]

    return as_lists(inferred), as_lists(approved), as_lists(unexpected)


def output_reports_inconsistency(output: str) -> bool:
    return any(pattern.search(output) for pattern in _INCONSISTENCY_PATTERNS)


def unsatisfiable_classes_from_robot_output(output: str) -> list[str]:
    """Extract ROBOT 1.9.7's exact ``unsatisfiable: <IRI>`` records."""

    pattern = re.compile(
        r"^(?:[^\r\n]*\s-\s+)?\s*unsatisfiable:\s*"
        r"(?:<(https?://[^>\s]+|urn:[^>\s]+)>|"
        r"((?:https?://|urn:)[^\s]+)|"
        r"([A-Za-z][\w.-]*:[A-Za-z_][\w.-]*))\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    found: set[str] = set()
    for match in pattern.finditer(output):
        value = next(group for group in match.groups() if group is not None)
        normalized = _normalize_named_class(value)
        if normalized is not None:
            found.add(normalized)
    return sorted(found)


def classify_reasoner_status(
    *,
    executed: bool,
    exit_code: int | None,
    output: str = "",
    reasoned_output_ready: bool = False,
    unsatisfiable_named_classes: Sequence[str] = (),
    equivalence_check_ran: bool = False,
    unexpected_equivalent_classes: Sequence[Sequence[str]] = (),
) -> tuple[str, str]:
    """Map process/check evidence to the Stage 03 status model."""

    if not executed:
        return STATUS_NOT_RUN, UNKNOWN
    if output_reports_inconsistency(output):
        return STATUS_FAIL_INCONSISTENT, INCONSISTENT
    if unsatisfiable_named_classes:
        return STATUS_FAIL_UNSATISFIABLE_CLASSES, CONSISTENT
    if exit_code != 0:
        return STATUS_FAIL_TOOL_ERROR, UNKNOWN
    if not reasoned_output_ready:
        return STATUS_FAIL_TOOL_ERROR, UNKNOWN
    if not equivalence_check_ran:
        return STATUS_FAIL_TOOL_ERROR, CONSISTENT
    if unexpected_equivalent_classes:
        return STATUS_FAIL_UNEXPECTED_EQUIVALENCES, CONSISTENT
    return STATUS_PASS, CONSISTENT


def find_portability_violations(text: str) -> list[str]:
    # HTTP(S) URLs are portable references, even if their URL path happens to
    # contain a platform-looking segment. Scan only the non-URL text.
    without_urls = re.sub(r"https?://[^\s`\"'<>]+", "", text)
    return [
        name
        for name, pattern in _PORTABILITY_PATTERNS
        if pattern.search(without_urls)
    ]


def _relative_artifact(path: Path, root: Path = ROOT) -> str:
    return path.relative_to(root).as_posix()


def _allowlist_hash(path: Path = ALLOWLIST_PATH) -> str:
    return sha256_bytes(_normalized_source_bytes(path))


def _initial_runtime_record(
    *,
    root: Path,
    runtime_dir: Path,
    semantic_hash: str,
    input_file_hash: str,
) -> dict[str, Any]:
    source_files = [
        path.relative_to(root).as_posix()
        for path in release_source_files(root, include_alignments=False)
    ]
    return {
        "runtime_schema_version": 1,
        "status": STATUS_NOT_RUN,
        "ontology_version": ontology_version(root),
        "root_ontology_iri": _load_module_config(root)["root"]["ontology_iri"],
        "release_source_hash": ontology_release_source_hash(root),
        "release_source_files": source_files,
        "release_source_includes_optional_alignments": False,
        "reasoner_input_semantic_hash": semantic_hash,
        "reasoner_input_file_hash": input_file_hash,
        "reasoner_allowlist_hash": _allowlist_hash(root / "config" / "reasoner-allowlist.yaml"),
        "rdflib_version": installed_rdflib_version(),
        "robot_version": ROBOT_VERSION,
        "robot_sha256": "",
        "robot_expected_sha256": EXPECTED_ROBOT_SHA256,
        "robot_download_url": ROBOT_URL,
        "reasoner": "HermiT",
        "hermit_version": UNKNOWN,
        "java_version": UNKNOWN,
        "exit_code": None,
        "consistency": UNKNOWN,
        "unsatisfiable_check": STATUS_NOT_RUN,
        "unsatisfiable_named_classes": [],
        "unexpected_equivalent_class_check": STATUS_NOT_RUN,
        "inferred_equivalent_classes": [],
        "allowed_inferred_equivalent_classes": [],
        "unexpected_equivalent_classes": [],
        "warnings": [],
        "execution_command": PORTABLE_EXECUTION_COMMAND,
        "robot_command": PORTABLE_ROBOT_COMMAND,
        "executed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "execution_time_seconds": 0.0,
        "reasoned_output_generated": False,
        "reasoned_output_file_hash": "",
        "artifacts": {
            "reasoner_input": _relative_artifact(runtime_dir / "reasoner-input.nt", root),
            "reasoned_ontology": _relative_artifact(runtime_dir / "reasoned-ontology.owl", root),
            "unsatisfiable_classes": _relative_artifact(runtime_dir / "unsatisfiable.txt", root),
            "unsatisfiable_debug_ontology": _relative_artifact(runtime_dir / "unsatisfiable-debug.owl", root),
            "unexpected_equivalences": _relative_artifact(runtime_dir / "unexpected-equivalences.json", root),
        },
    }


def _write_equivalence_report(
    path: Path,
    *,
    check: str,
    inferred: Sequence[Sequence[str]] = (),
    approved: Sequence[Sequence[str]] = (),
    unexpected: Sequence[Sequence[str]] = (),
) -> None:
    write_json(
        path,
        {
            "check": check,
            "inferred_equivalent_classes": list(inferred),
            "allowed_inferred_equivalent_classes": list(approved),
            "unexpected_equivalent_classes": list(unexpected),
        },
    )


def _finish_runtime_record(
    report: dict[str, Any],
    *,
    started: float,
    report_path: Path,
) -> int:
    report["execution_time_seconds"] = round(time.perf_counter() - started, 6)
    write_json(report_path, report)
    print(f"Reasoner status: {report['status']}")
    print(f"Runtime report: {_relative_artifact(report_path)}")
    if report["status"] == STATUS_PASS:
        return 0
    return 2 if report["status"] == STATUS_NOT_RUN else 1


def run_reasoner(
    *,
    root: Path = ROOT,
    runtime_dir: Path | None = None,
    download_dir: Path | None = None,
) -> int:
    """Execute HermiT and write ignored, machine-readable runtime artifacts."""

    started = time.perf_counter()
    active_runtime = runtime_dir if runtime_dir is not None else root / "runtime_reports" / "ontology"
    active_download = download_dir if download_dir is not None else root / "third_party" / "downloads"
    active_runtime.mkdir(parents=True, exist_ok=True)
    input_path = active_runtime / "reasoner-input.nt"
    reasoned_path = active_runtime / "reasoned-ontology.owl"
    debug_path = active_runtime / "unsatisfiable-debug.owl"
    unsat_path = active_runtime / "unsatisfiable.txt"
    equivalence_path = active_runtime / "unexpected-equivalences.json"
    report_path = active_runtime / "reasoner-run.json"

    for stale in (reasoned_path, debug_path, unsat_path, equivalence_path):
        stale.unlink(missing_ok=True)

    try:
        if installed_rdflib_version() != EXPECTED_RDFLIB_VERSION:
            raise RuntimeError(
                "RDFLib version mismatch for canonical hashing: "
                f"expected {EXPECTED_RDFLIB_VERSION}, got {installed_rdflib_version()}"
            )
        asserted, semantic_hash, input_file_hash = write_reasoner_input(
            input_path,
            root=root,
        )
        report = _initial_runtime_record(
            root=root,
            runtime_dir=active_runtime,
            semantic_hash=semantic_hash,
            input_file_hash=input_file_hash,
        )
    except Exception as exc:  # noqa: BLE001 - must persist honest NOT_RUN evidence
        report = {
            "runtime_schema_version": 1,
            "status": STATUS_NOT_RUN,
            "consistency": UNKNOWN,
            "exit_code": None,
            "unsatisfiable_check": STATUS_NOT_RUN,
            "unexpected_equivalent_class_check": STATUS_NOT_RUN,
            "warnings": [f"reasoner input preparation failed: {exc}"],
            "execution_time_seconds": 0.0,
        }
        return _finish_runtime_record(report, started=started, report_path=report_path)

    try:
        jar = ensure_robot(download_dir=active_download)
        report["robot_sha256"] = sha256_file(jar)
        embedded_robot = robot_embedded_version(jar)
        if embedded_robot not in {ROBOT_VERSION, UNKNOWN}:
            raise RuntimeError(
                f"embedded ROBOT version is {embedded_robot}, expected {ROBOT_VERSION}"
            )
        report["hermit_version"] = hermit_version_from_robot(jar)
    except Exception as exc:  # noqa: BLE001 - download/checksum errors are NOT_RUN
        report["warnings"] = [f"ROBOT unavailable: {exc}"]
        write_unsatisfiable_report(unsat_path, [])
        _write_equivalence_report(equivalence_path, check=STATUS_NOT_RUN)
        return _finish_runtime_record(report, started=started, report_path=report_path)

    report["java_version"] = java_version()
    command = [
        "java",
        "-jar",
        str(jar),
        "reason",
        "--input",
        str(input_path),
        "--reasoner",
        "hermit",
        "--equivalent-classes-allowed",
        "all",
        "--axiom-generators",
        "SubClass EquivalentClass",
        "--dump-unsatisfiable",
        str(debug_path),
        "--output",
        str(reasoned_path),
    ]

    try:
        process = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        report["warnings"] = [f"Java execution failed before the reasoner ran: {exc}"]
        write_unsatisfiable_report(unsat_path, [])
        _write_equivalence_report(equivalence_path, check=STATUS_NOT_RUN)
        return _finish_runtime_record(report, started=started, report_path=report_path)

    report["exit_code"] = process.returncode
    combined_output = "\n".join(
        part.strip() for part in (process.stdout, process.stderr) if part and part.strip()
    )
    logged_unsatisfiable = unsatisfiable_classes_from_robot_output(combined_output)

    if (
        process.returncode != 0
        or output_reports_inconsistency(combined_output)
        or logged_unsatisfiable
    ):
        status, consistency = classify_reasoner_status(
            executed=True,
            exit_code=process.returncode,
            output=combined_output,
            unsatisfiable_named_classes=logged_unsatisfiable,
        )
        report["status"] = status
        report["consistency"] = consistency
        report["unsatisfiable_check"] = (
            STATUS_FAIL_UNSATISFIABLE_CLASSES
            if logged_unsatisfiable
            else STATUS_NOT_RUN
        )
        report["unsatisfiable_named_classes"] = logged_unsatisfiable
        report["warnings"] = [combined_output[-2000:]] if combined_output else []
        write_unsatisfiable_report(unsat_path, logged_unsatisfiable)
        _write_equivalence_report(equivalence_path, check=STATUS_NOT_RUN)
        return _finish_runtime_record(report, started=started, report_path=report_path)

    if not reasoned_path.is_file() or reasoned_path.stat().st_size == 0:
        report["status"], report["consistency"] = classify_reasoner_status(
            executed=True,
            exit_code=process.returncode,
            output=combined_output,
            reasoned_output_ready=False,
        )
        report["warnings"] = ["ROBOT did not create a reasoned ontology"]
        write_unsatisfiable_report(unsat_path, [])
        _write_equivalence_report(equivalence_path, check=STATUS_NOT_RUN)
        return _finish_runtime_record(report, started=started, report_path=report_path)

    try:
        reasoned = Graph()
        reasoned.parse(reasoned_path)
        unsatisfiable = sorted(
            set(find_unsatisfiable_named_classes(reasoned))
            | set(logged_unsatisfiable)
        )
        write_unsatisfiable_report(unsat_path, unsatisfiable)
        # Parse our normalized artifact back so the persisted evidence is part
        # of the gate, rather than trusting only in-memory values.
        persisted_unsatisfiable = parse_unsatisfiable_file(unsat_path)
        if persisted_unsatisfiable != unsatisfiable:
            raise RuntimeError("normalized unsatisfiable-class report mismatch")

        allowlist_path = root / "config" / "reasoner-allowlist.yaml"
        allowlist = load_equivalence_allowlist(allowlist_path)
        inferred, approved, unexpected = detect_inferred_equivalent_classes(
            asserted,
            reasoned,
            allowlist,
        )
        equivalence_check = STATUS_PASS if not unexpected else STATUS_FAIL_UNEXPECTED_EQUIVALENCES
        _write_equivalence_report(
            equivalence_path,
            check=equivalence_check,
            inferred=inferred,
            approved=approved,
            unexpected=unexpected,
        )
    except Exception as exc:  # noqa: BLE001 - analysis errors are tool errors
        report["status"] = STATUS_FAIL_TOOL_ERROR
        report["consistency"] = CONSISTENT
        report["warnings"] = [f"reasoner output analysis failed: {exc}"]
        if not unsat_path.is_file():
            write_unsatisfiable_report(unsat_path, [])
        if not equivalence_path.is_file():
            _write_equivalence_report(equivalence_path, check=STATUS_NOT_RUN)
        return _finish_runtime_record(report, started=started, report_path=report_path)

    status, consistency = classify_reasoner_status(
        executed=True,
        exit_code=process.returncode,
        output=combined_output,
        reasoned_output_ready=True,
        unsatisfiable_named_classes=unsatisfiable,
        equivalence_check_ran=True,
        unexpected_equivalent_classes=unexpected,
    )
    report.update(
        {
            "status": status,
            "consistency": consistency,
            "unsatisfiable_check": (
                STATUS_PASS if not unsatisfiable else STATUS_FAIL_UNSATISFIABLE_CLASSES
            ),
            "unsatisfiable_named_classes": unsatisfiable,
            "unexpected_equivalent_class_check": equivalence_check,
            "inferred_equivalent_classes": inferred,
            "allowed_inferred_equivalent_classes": approved,
            "unexpected_equivalent_classes": unexpected,
            "reasoned_output_generated": True,
            "reasoned_output_file_hash": sha256_file(reasoned_path),
            "warnings": [],
        }
    )
    return _finish_runtime_record(report, started=started, report_path=report_path)


def _expected_artifact_paths(root: Path, runtime_dir: Path) -> dict[str, Path]:
    return {
        "reasoner_input": runtime_dir / "reasoner-input.nt",
        "reasoned_ontology": runtime_dir / "reasoned-ontology.owl",
        "unsatisfiable_classes": runtime_dir / "unsatisfiable.txt",
        "unsatisfiable_debug_ontology": runtime_dir / "unsatisfiable-debug.owl",
        "unexpected_equivalences": runtime_dir / "unexpected-equivalences.json",
    }


def validate_runtime_report(
    report: Mapping[str, Any],
    *,
    root: Path = ROOT,
    runtime_dir: Path | None = None,
    download_dir: Path | None = None,
) -> list[str]:
    active_runtime = runtime_dir if runtime_dir is not None else root / "runtime_reports" / "ontology"
    active_download = download_dir if download_dir is not None else root / "third_party" / "downloads"
    errors: list[str] = []

    expected_scalars = {
        "runtime_schema_version": 1,
        "status": STATUS_PASS,
        "ontology_version": ontology_version(root),
        "root_ontology_iri": _load_module_config(root)["root"]["ontology_iri"],
        "release_source_hash": ontology_release_source_hash(root),
        "release_source_includes_optional_alignments": False,
        "reasoner_allowlist_hash": _allowlist_hash(root / "config" / "reasoner-allowlist.yaml"),
        "rdflib_version": EXPECTED_RDFLIB_VERSION,
        "robot_version": ROBOT_VERSION,
        "robot_sha256": EXPECTED_ROBOT_SHA256,
        "robot_expected_sha256": EXPECTED_ROBOT_SHA256,
        "robot_download_url": ROBOT_URL,
        "reasoner": "HermiT",
        "exit_code": 0,
        "consistency": CONSISTENT,
        "unsatisfiable_check": STATUS_PASS,
        "unexpected_equivalent_class_check": STATUS_PASS,
        "reasoned_output_generated": True,
        "execution_command": PORTABLE_EXECUTION_COMMAND,
        "robot_command": PORTABLE_ROBOT_COMMAND,
    }
    for field, expected in expected_scalars.items():
        actual = report.get(field)
        if actual != expected:
            errors.append(f"{field}: expected {expected!r}, got {actual!r}")

    expected_sources = [
        path.relative_to(root).as_posix()
        for path in release_source_files(root, include_alignments=False)
    ]
    if report.get("release_source_files") != expected_sources:
        errors.append("release_source_files: does not match the default runtime release profile")

    for field in ("unsatisfiable_named_classes", "unexpected_equivalent_classes"):
        if report.get(field) != []:
            errors.append(f"{field}: expected an empty list, got {report.get(field)!r}")

    if not isinstance(report.get("hermit_version"), str) or not report.get("hermit_version"):
        errors.append("hermit_version: missing")
    if not isinstance(report.get("java_version"), str) or not report.get("java_version"):
        errors.append("java_version: missing")
    elif (major := java_major_version(str(report["java_version"]))) is None or major < 17:
        errors.append(
            f"java_version: Java 17 or newer is required, got {report.get('java_version')!r}"
        )

    jar = active_download / ROBOT_JAR_NAME
    if not jar.is_file():
        errors.append("robot_sha256: checksum-pinned cache JAR is missing")
    else:
        actual_robot_sha = sha256_file(jar)
        if actual_robot_sha != EXPECTED_ROBOT_SHA256:
            errors.append(
                "robot_sha256: cached JAR does not match the hard-coded trust anchor"
            )
        embedded_robot = robot_embedded_version(jar)
        if embedded_robot not in {ROBOT_VERSION, UNKNOWN}:
            errors.append(
                f"robot_version: embedded metadata is {embedded_robot!r}, expected {ROBOT_VERSION!r}"
            )
        embedded_hermit = hermit_version_from_robot(jar)
        if report.get("hermit_version") != embedded_hermit:
            errors.append(
                f"hermit_version: runtime={report.get('hermit_version')!r}, "
                f"embedded dependency={embedded_hermit!r}"
            )

    command_text = f"{report.get('execution_command', '')}\n{report.get('robot_command', '')}"
    for violation in find_portability_violations(command_text):
        errors.append(f"portable command: contains {violation}")

    artifacts = report.get("artifacts")
    expected_paths = _expected_artifact_paths(root, active_runtime)
    if not isinstance(artifacts, dict):
        errors.append("artifacts: expected an object")
        artifacts = {}
    for key, path in expected_paths.items():
        expected_relative = _relative_artifact(path, root)
        if artifacts.get(key) != expected_relative:
            errors.append(
                f"artifacts.{key}: expected {expected_relative!r}, got {artifacts.get(key)!r}"
            )

    input_path = expected_paths["reasoner_input"]
    if not input_path.is_file():
        errors.append("reasoner_input_file_hash: reasoner input file is missing")
    else:
        actual_file_hash = sha256_file(input_path)
        if report.get("reasoner_input_file_hash") != actual_file_hash:
            errors.append(
                "reasoner_input_file_hash: runtime report does not match the actual input file"
            )
        try:
            input_graph = Graph()
            input_graph.parse(input_path, format="nt")
            actual_semantic_hash = reasoner_input_semantic_hash(input_graph)
            if report.get("reasoner_input_semantic_hash") != actual_semantic_hash:
                errors.append(
                    "reasoner_input_semantic_hash: runtime report does not match the actual input graph"
                )
            expected_semantic_hash = reasoner_input_semantic_hash(
                asserted_reasoner_graph(root)
            )
            if actual_semantic_hash != expected_semantic_hash:
                errors.append(
                    "reasoner_input_semantic_hash: actual input does not match the current formal runtime modules"
                )
            if input_path.read_bytes() != canonical_graph_bytes(input_graph):
                errors.append(
                    "reasoner_input_file_hash: actual input is not canonical sorted N-Triples"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"reasoner_input_semantic_hash: input graph cannot be parsed: {exc}")

    reasoned_path = expected_paths["reasoned_ontology"]
    if not reasoned_path.is_file():
        errors.append("reasoned_output_file_hash: reasoned ontology is missing")
    elif report.get("reasoned_output_file_hash") != sha256_file(reasoned_path):
        errors.append("reasoned_output_file_hash: report does not match reasoned ontology")
    else:
        try:
            reasoned_graph = Graph()
            reasoned_graph.parse(reasoned_path)
            recomputed_unsatisfiable = find_unsatisfiable_named_classes(
                reasoned_graph
            )
            if recomputed_unsatisfiable != report.get("unsatisfiable_named_classes"):
                errors.append(
                    "unsatisfiable_named_classes: runtime report does not match the reasoned ontology"
                )
            recomputed_inferred, recomputed_approved, recomputed_unexpected = (
                detect_inferred_equivalent_classes(
                    asserted_reasoner_graph(root),
                    reasoned_graph,
                    load_equivalence_allowlist(
                        root / "config" / "reasoner-allowlist.yaml"
                    ),
                )
            )
            for field, recomputed in (
                ("inferred_equivalent_classes", recomputed_inferred),
                ("allowed_inferred_equivalent_classes", recomputed_approved),
                ("unexpected_equivalent_classes", recomputed_unexpected),
            ):
                if report.get(field) != recomputed:
                    errors.append(
                        f"{field}: runtime report does not match the reasoned ontology"
                    )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"reasoned ontology: cannot recompute logical checks: {exc}")

    unsat_path = expected_paths["unsatisfiable_classes"]
    try:
        persisted_unsat = parse_unsatisfiable_file(unsat_path)
        if persisted_unsat != report.get("unsatisfiable_named_classes"):
            errors.append("unsatisfiable_named_classes: normalized artifact mismatch")
    except UnsatisfiableReportError as exc:
        errors.append(f"unsatisfiable_named_classes: {exc}")

    equivalence_path = expected_paths["unexpected_equivalences"]
    if not equivalence_path.is_file():
        errors.append("unexpected_equivalent_classes: artifact is missing")
    else:
        try:
            equivalence = read_json(equivalence_path)
            for field in (
                "inferred_equivalent_classes",
                "allowed_inferred_equivalent_classes",
                "unexpected_equivalent_classes",
            ):
                if equivalence.get(field) != report.get(field):
                    errors.append(f"{field}: runtime and equivalence artifact differ")
            if equivalence.get("check") != STATUS_PASS:
                errors.append(
                    f"unexpected_equivalent_class_check: artifact is {equivalence.get('check')!r}"
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"unexpected_equivalent_classes: invalid artifact: {exc}")

    if any(value == STATUS_NOT_RUN for value in report.values()):
        errors.append("runtime report contains NOT_RUN")
    if report.get("consistency") == UNKNOWN:
        errors.append("consistency: UNKNOWN is not a passing result")
    return errors


ATTESTATION_FIELDS = (
    "ontology_version",
    "root_ontology_iri",
    "release_source_hash",
    "release_source_files",
    "release_source_includes_optional_alignments",
    "reasoner_input_semantic_hash",
    "reasoner_input_file_hash",
    "reasoner_allowlist_hash",
    "rdflib_version",
    "robot_version",
    "robot_sha256",
    "robot_download_url",
    "reasoner",
    "hermit_version",
    "java_version",
    "consistency",
    "unsatisfiable_check",
    "unsatisfiable_named_classes",
    "unexpected_equivalent_class_check",
    "inferred_equivalent_classes",
    "allowed_inferred_equivalent_classes",
    "unexpected_equivalent_classes",
    "execution_command",
    "robot_command",
    "warnings",
    "status",
)


def attestation_from_runtime(report: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in ATTESTATION_FIELDS if field not in report]
    if missing:
        raise ValueError(f"runtime report missing attestation fields: {', '.join(missing)}")
    attestation = {field: report[field] for field in ATTESTATION_FIELDS}
    attestation["attestation_schema_version"] = 1
    return attestation


def _markdown_pairs(pairs: Sequence[Sequence[str]]) -> list[str]:
    if not pairs:
        return ["- (none)"]
    return [f"- `{pair[0]}` = `{pair[1]}`" for pair in pairs]


def render_reasoner_markdown(attestation: Mapping[str, Any]) -> str:
    unsatisfiable = attestation.get("unsatisfiable_named_classes", [])
    warnings = attestation.get("warnings", [])
    lines = [
        "# OWL 2 DL Reasoner Attestation",
        "",
        f"- Status: `{attestation['status']}`",
        f"- Ontology release version: `{attestation['ontology_version']}`",
        f"- Root ontology IRI: `{attestation['root_ontology_iri']}`",
        f"- Release source hash (SHA-256): `{attestation['release_source_hash']}`",
        "- Release source includes optional alignments: `false`",
        f"- Reasoner input semantic hash (SHA-256): `{attestation['reasoner_input_semantic_hash']}`",
        f"- Reasoner input file hash (SHA-256): `{attestation['reasoner_input_file_hash']}`",
        f"- Reasoner allowlist hash (SHA-256): `{attestation['reasoner_allowlist_hash']}`",
        f"- RDFLib version (canonicalization): `{attestation['rdflib_version']}`",
        f"- ROBOT version: `{attestation['robot_version']}`",
        f"- ROBOT JAR SHA-256: `{attestation['robot_sha256']}`",
        f"- ROBOT download URL: `{attestation['robot_download_url']}`",
        f"- Reasoner name: `{attestation['reasoner']}`",
        f"- HermiT version: `{attestation['hermit_version']}`",
        f"- Java version: `{attestation['java_version']}`",
        f"- Consistency: `{attestation['consistency']}`",
        f"- Unsatisfiable named-class check: `{attestation['unsatisfiable_check']}`",
        f"- Unexpected equivalent-class check: `{attestation['unexpected_equivalent_class_check']}`",
        f"- Execution command: `{attestation['execution_command']}`",
        "",
        "The underlying portable ROBOT command template is:",
        "",
        "```text",
        str(attestation["robot_command"]),
        "```",
        "",
        "## Unsatisfiable named classes",
        "",
    ]
    lines.extend(f"- `{item}`" for item in unsatisfiable)
    if not unsatisfiable:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "## Unexpected inferred equivalent classes",
            "",
            *_markdown_pairs(attestation.get("unexpected_equivalent_classes", [])),
            "",
            "## Allowlisted inferred equivalent classes",
            "",
            *_markdown_pairs(attestation.get("allowed_inferred_equivalent_classes", [])),
            "",
            "## Warnings",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in warnings)
    if not warnings:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "This Markdown file is generated deterministically from",
            "`docs/ontology/reasoner-attestation.json`; do not edit it independently.",
            "Runtime-only evidence is written under `runtime_reports/ontology/`.",
            "",
        ]
    )
    return "\n".join(lines)


def update_attestation(
    *,
    root: Path = ROOT,
    runtime_dir: Path | None = None,
) -> int:
    active_runtime = runtime_dir if runtime_dir is not None else root / "runtime_reports" / "ontology"
    runtime_path = active_runtime / "reasoner-run.json"
    if not runtime_path.is_file():
        print(f"Cannot update attestation: missing {_relative_artifact(runtime_path, root)}")
        return 1
    try:
        report = read_json(runtime_path)
        errors = validate_runtime_report(report, root=root, runtime_dir=active_runtime)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot update attestation: {exc}")
        return 1
    if errors:
        print("Cannot update attestation from a failing runtime report:")
        for error in errors:
            print(f"- {error}")
        return 1

    attestation = attestation_from_runtime(report)
    attestation_path = root / "docs" / "ontology" / "reasoner-attestation.json"
    markdown_path = root / "docs" / "ontology" / "reasoner-report.md"
    write_json(attestation_path, attestation)
    _write_text_bytes(markdown_path, render_reasoner_markdown(attestation))
    print(f"Updated {_relative_artifact(attestation_path, root)}")
    print(f"Updated {_relative_artifact(markdown_path, root)}")
    return 0


def verify_robot_checksum() -> int:
    try:
        jar = ensure_robot()
    except Exception as exc:  # noqa: BLE001
        print(f"ROBOT checksum verification failed: {exc}")
        return 1
    actual = sha256_file(jar)
    print(f"ROBOT version: {ROBOT_VERSION}")
    print(f"ROBOT SHA-256: {actual}")
    print(f"HermiT version: {hermit_version_from_robot(jar)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--verify-robot-checksum",
        action="store_true",
        help="download if missing and verify the fixed ROBOT SHA-256",
    )
    actions.add_argument(
        "--update-attestation",
        action="store_true",
        help="promote a verified runtime result to tracked JSON/Markdown proof",
    )
    args = parser.parse_args()
    if args.verify_robot_checksum:
        return verify_robot_checksum()
    if args.update_attestation:
        return update_attestation()
    return run_reasoner()


if __name__ == "__main__":
    raise SystemExit(main())
