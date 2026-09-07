"""Wheel-resource-based deterministic compiler snapshot."""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import zipfile
from importlib import resources
from pathlib import Path
from typing import Any

from kg_mnp import __version__ as toolchain_version
from kg_mnp.contracts.canonical import semantic_hash, stable_urn

from .contracts import finalize_artifact
from .version import COMPILER_VERSION

ROBOT_VERSION = "1.9.7"
ROBOT_SHA256 = "91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d"
HERMIT_VERSION = "1.4.5.456"
HERMIT_POM = "META-INF/maven/net.sourceforge.owlapi/org.semanticweb.hermit/pom.properties"

IMPLEMENTATION_FILES = (
    "semantic_kernel/abox.py",
    "semantic_kernel/artifact_resolver.py",
    "semantic_kernel/artifacts.py",
    "semantic_kernel/baseline.py",
    "semantic_kernel/cli.py",
    "semantic_kernel/compiler.py",
    "semantic_kernel/contracts.py",
    "semantic_kernel/errors.py",
    "semantic_kernel/evidence_lineage.py",
    "semantic_kernel/graph_roles.py",
    "semantic_kernel/identifiers.py",
    "semantic_kernel/input_attestation.py",
    "semantic_kernel/limits.py",
    "semantic_kernel/literals.py",
    "semantic_kernel/mapping.py",
    "semantic_kernel/models.py",
    "semantic_kernel/namespaces.py",
    "semantic_kernel/packaging/archive.py",
    "semantic_kernel/packaging/export.py",
    "semantic_kernel/packaging/locking.py",
    "semantic_kernel/packaging/manifest.py",
    "semantic_kernel/packaging/verifier.py",
    "semantic_kernel/plan.py",
    "semantic_kernel/policy.py",
    "semantic_kernel/provenance.py",
    "semantic_kernel/reasoner.py",
    "semantic_kernel/rdf/canonical.py",
    "semantic_kernel/rdf/dataset.py",
    "semantic_kernel/rdf/parser.py",
    "semantic_kernel/rdf/skolem.py",
    "semantic_kernel/rdf/serializers.py",
    "semantic_kernel/review_audit.py",
    "semantic_kernel/security.py",
    "semantic_kernel/shacl.py",
    "semantic_kernel/snapshot.py",
    "semantic_kernel/tbox.py",
    "semantic_kernel/transaction.py",
    "semantic_kernel/validation.py",
    "semantic_kernel/validators/competency_questions.py",
    "semantic_kernel/validators/owl_consistency.py",
    "semantic_kernel/validators/owl_profile.py",
    "semantic_kernel/validators/provenance.py",
    "semantic_kernel/validators/rdf_syntax.py",
    "semantic_kernel/validators/shacl.py",
    "semantic_kernel/version.py",
)


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "UNAVAILABLE"


def _hermit_version(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            content = archive.read(HERMIT_POM).decode("iso-8859-1")
    except (OSError, KeyError, zipfile.BadZipFile):
        return "UNKNOWN"
    for line in content.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "version":
            return value.strip()
    return "UNKNOWN"


def build_compiler_snapshot(policy: dict[str, Any], *, reasoner_jar: Path | str | None = None) -> dict[str, Any]:
    if policy["compiler_version"] != COMPILER_VERSION:
        raise ValueError("compiler policy targets a different semantic compiler version")
    package = resources.files("kg_mnp")
    files = []
    for relative in IMPLEMENTATION_FILES:
        raw = package.joinpath(relative).read_bytes()
        files.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest()})
    implementation_digest = semantic_hash(files)
    reasoner_path = Path(reasoner_jar).resolve(strict=True) if reasoner_jar is not None else None
    available = False
    hermit = HERMIT_VERSION
    if reasoner_path is not None and reasoner_path.is_file():
        actual = hashlib.sha256(reasoner_path.read_bytes()).hexdigest()
        hermit = _hermit_version(reasoner_path)
        if actual != ROBOT_SHA256 or hermit != HERMIT_VERSION:
            raise ValueError("trusted reasoner bundle digest or HermiT dependency mismatch")
        available = True
    dependencies = [
        {"name": name, "version": _version(name)}
        for name in ("rdflib", "pyshacl", "owlrl", "jsonschema", "PyYAML")
    ]
    core = {
        "manifest_kind": "KG_MNP_SEMANTIC_COMPILER_SNAPSHOT",
        "schema_version": "1.1.0",
        "compiler_id": stable_urn("semantic-compiler", {"version": COMPILER_VERSION}),
        "compiler_version": COMPILER_VERSION,
        "toolchain_version": toolchain_version,
        "policy_id": policy["policy_id"],
        "policy_semantic_sha256": policy["content_digest"],
        "canonicalization_profile": policy["canonicalization_profile"],
        "skolemization_profile": policy["skolemization_profile"],
        "implementation_files": files,
        "implementation_digest": implementation_digest,
        "python_version": platform.python_version(),
        "dependency_versions": dependencies,
        "reasoner_bundle": {"engine": "HermiT", "robot_version": ROBOT_VERSION, "robot_jar_sha256": ROBOT_SHA256, "hermit_version": hermit, "java_requirement": "Java 11+", "availability": "AVAILABLE" if available else "UNAVAILABLE", "validation_profile": policy["owl_profile_policy"]},
        "validation_engines": [{"name": "pyshacl", "version": _version("pyshacl")}, {"name": "ROBOT-HermiT", "version": f"{ROBOT_VERSION}/{HERMIT_VERSION}"}],
    }
    return finalize_artifact(core, id_field="snapshot_id", urn_kind="semantic-compiler-snapshot", contract="semantic-compiler-snapshot")
