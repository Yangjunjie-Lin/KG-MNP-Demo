from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF


class ConversionError(ValueError):
    pass


def _validate_local_imports(paths: list[Path]) -> None:
    """Require every owl:imports edge to resolve to a mounted local file."""
    ontology_iris: dict[str, Path] = {}
    imports_by_path: dict[Path, set[str]] = {}
    for path in paths:
        graph = Graph()
        try:
            graph.parse(path.as_posix(), format="turtle")
        except Exception as exc:
            raise ConversionError(
                f"cannot inspect OWL imports in local source: {path}"
            ) from exc
        for subject in graph.subjects(RDF.type, OWL.Ontology):
            if not isinstance(subject, URIRef):
                raise ConversionError("OWL ontology declaration must use an IRI")
            iri = str(subject)
            if iri in ontology_iris and ontology_iris[iri] != path:
                raise ConversionError(f"duplicate local ontology IRI: {iri}")
            ontology_iris[iri] = path
        imports: set[str] = set()
        for subject in graph.subjects(OWL.imports, None):
            for imported in graph.objects(subject, OWL.imports):
                if not isinstance(imported, URIRef):
                    raise ConversionError(
                        f"OWL import is not an IRI in local source: {path}"
                    )
                imports.add(str(imported))
        imports_by_path[path] = imports
    known_iris = set(ontology_iris)
    for path, imports in imports_by_path.items():
        unresolved = sorted(imports - known_iris)
        if unresolved:
            raise ConversionError(
                "OWL imports are not resolved by explicit local dependencies: "
                + ", ".join(unresolved)
            )


def _extract_json(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(value, dict)
            and "classAttribute" in value
            and "propertyAttribute" in value
        ):
            return value
    raise ConversionError("OWL2VOWL did not emit a VOWL JSON object")


def convert_with_owl2vowl_docker(
    source: Mapping[str, Any], *, image: str, timeout: float = 180.0
) -> dict[str, Any]:
    """Execute frozen OWL2VOWL with local read-only sources and no network."""
    requested_root = Path(source["root"])
    if requested_root.is_symlink() or bool(
        getattr(requested_root, "is_junction", lambda: False)()
    ):
        raise ConversionError("unsafe OWL2VOWL authority root")
    root = requested_root.resolve()
    records = list(source.get("files", []))
    if any(not isinstance(item, Mapping) for item in records):
        raise ConversionError("OWL2VOWL source records must be objects")
    unknown_roles = {
        str(item.get("role"))
        for item in records
        if item.get("role") not in {"ROOT_ONTOLOGY", "RUNTIME_DEPENDENCY"}
    }
    if unknown_roles:
        raise ConversionError(
            "unsupported OWL2VOWL source roles: " + ", ".join(sorted(unknown_roles))
        )
    roots = [item for item in records if item.get("role") == "ROOT_ONTOLOGY"]
    dependencies = [
        item for item in records if item.get("role") == "RUNTIME_DEPENDENCY"
    ]
    if len(roots) != 1:
        raise ConversionError("OWL2VOWL requires exactly one root ontology")

    def local_file(item: Mapping[str, Any]) -> Path:
        raw_path = item.get("path")
        if not isinstance(raw_path, str):
            raise ConversionError("OWL2VOWL source path must be text")
        relative = PurePosixPath(raw_path)
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in raw_path
            or ":" in relative.parts[0]
        ):
            raise ConversionError("unsafe OWL2VOWL source path")
        candidate = root.joinpath(*relative.parts)
        current = root
        for part in relative.parts:
            current /= part
            is_junction = bool(getattr(current, "is_junction", lambda: False)())
            if current.is_symlink() or is_junction:
                raise ConversionError("unsafe OWL2VOWL source path")
        try:
            path = candidate.resolve(strict=True)
        except OSError as exc:
            raise ConversionError("OWL2VOWL source file is unavailable") from exc
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or candidate.is_symlink()
            or "," in str(path)
        ):
            raise ConversionError("unsafe OWL2VOWL source path")
        expected = item.get("sha256")
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise ConversionError("OWL2VOWL source file is unavailable") from exc
        if not isinstance(expected, str) or len(expected) != 64 or actual != expected:
            raise ConversionError("OWL2VOWL source file hash mismatch")
        return path

    root_file = local_file(roots[0])
    # Preserve the Stage 03 baseline order: it is content-locked and is part of
    # the independently audited raw OWL2VOWL output.
    dependency_files = [local_file(item) for item in dependencies]
    all_files = [root_file, *dependency_files]
    if len(all_files) != len(set(all_files)):
        raise ConversionError("duplicate OWL2VOWL source file")
    _validate_local_imports(all_files)

    root_target = "/kg-mnp-root-ontology" + root_file.suffix
    dependency_targets = [
        f"/kg-mnp-dependency-{index:03d}{path.suffix}"
        for index, path in enumerate(dependency_files, start=1)
    ]

    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "1000:1000",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
    ]
    # Mount only the authoritative ontology files.  Mounting `source["root"]`
    # would expose the repository, credentials, runtime reports, and any
    # unrelated untracked content to the converter process.
    for local, target in zip(all_files, [root_target, *dependency_targets]):
        command.extend(
            [
                "--mount",
                f"type=bind,source={local},target={target},readonly",
            ]
        )
    command.extend(
        [
            image,
            "java",
            "-jar",
            "/build/owl2vowl/target/OWL2VOWL-0.3.7-shaded.jar",
            "-echo",
            "-file",
            root_target,
        ]
    )
    if dependency_targets:
        command.extend(["-dependencies", *dependency_targets])
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=timeout,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ConversionError(f"frozen OWL2VOWL conversion failed: {exc}") from exc
    return _extract_json(completed.stdout)
