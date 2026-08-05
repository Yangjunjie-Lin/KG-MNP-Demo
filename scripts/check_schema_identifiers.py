#!/usr/bin/env python3
"""Validate repository JSON Schema identifiers without network access."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAMESPACE_CONFIG = ROOT / "config" / "namespaces.yaml"
SCHEMA_SCAN_ROOTS = ("schemas", "examples")
SCHEMA_FILE_SUFFIX = ".schema.json"
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
PROJECT_PAGES_BASE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/"


@dataclass(frozen=True)
class SchemaNamespaces:
    base: str
    modeling: str
    legacy: str


@dataclass(frozen=True)
class SchemaAuditResult:
    paths: tuple[str, ...]
    identifiers: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_absolute_https_uri(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.netloc) and bool(hostname)


def _contains_local_absolute_path(value: str) -> bool:
    if "\\" in value:
        return True
    try:
        path = urlsplit(value).path
    except ValueError:
        return True
    return bool(
        re.search(r"(?:^|/)[A-Za-z]:/", path)
        or re.search(r"(?:^|/)(?:Users|home)/[^/]+/", path, re.IGNORECASE)
    )


def load_schema_namespaces(
    path: Path = DEFAULT_NAMESPACE_CONFIG,
) -> SchemaNamespaces:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("namespace policy must be a mapping")
    schema_config = raw.get("schemas")
    if not isinstance(schema_config, dict):
        raise ValueError("namespace policy must define a schemas mapping")

    values: dict[str, str] = {}
    for key in ("base", "modeling", "legacy"):
        value = schema_config.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"schemas.{key} must be a non-empty string")
        if not value.endswith("/"):
            raise ValueError(f"schemas.{key} must end with '/': {value!r}")
        if not _is_absolute_https_uri(value):
            raise ValueError(f"schemas.{key} must be an absolute HTTPS URI: {value!r}")
        lowered = value.lower()
        if "example.org" in lowered or "localhost" in lowered or "file://" in lowered:
            raise ValueError(f"schemas.{key} uses a forbidden namespace: {value!r}")
        if _contains_local_absolute_path(value):
            raise ValueError(f"schemas.{key} contains a local absolute path: {value!r}")
        if not value.startswith(PROJECT_PAGES_BASE):
            raise ValueError(
                f"schemas.{key} must use the project GitHub Pages namespace: {value!r}"
            )
        values[key] = value

    if not values["modeling"].startswith(values["base"]):
        raise ValueError("schemas.modeling must be below schemas.base")
    if not values["legacy"].startswith(values["base"]):
        raise ValueError("schemas.legacy must be below schemas.base")
    if len(set(values.values())) != len(values):
        raise ValueError("schema namespaces must be distinct")
    return SchemaNamespaces(**values)


def tracked_and_intended_schema_files(
    root: Path = ROOT,
    scan_roots: tuple[str, ...] = SCHEMA_SCAN_ROOTS,
) -> tuple[Path, ...]:
    """Return existing tracked or non-ignored, untracked ``*.schema.json`` files."""

    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            *scan_roots,
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    relative_paths = completed.stdout.decode("utf-8").split("\0")
    return tuple(
        root / PurePosixPath(relative)
        for relative in sorted(set(relative_paths))
        if relative.endswith(SCHEMA_FILE_SUFFIX)
        and (root / PurePosixPath(relative)).is_file()
    )


def _validate_identifier(
    identifier: object,
    relative_path: str,
    namespaces: SchemaNamespaces,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(identifier, str) or not identifier:
        return [f"{relative_path}: $id must be a non-empty string"]
    if not _is_absolute_https_uri(identifier):
        errors.append(f"{relative_path}: $id must be an absolute HTTPS URI: {identifier!r}")
    lowered = identifier.lower()
    if "example.org" in lowered:
        errors.append(f"{relative_path}: $id must not use example.org: {identifier!r}")
    if "localhost" in lowered:
        errors.append(f"{relative_path}: $id must not use localhost: {identifier!r}")
    if "file://" in lowered:
        errors.append(f"{relative_path}: $id must not use file://: {identifier!r}")
    if _contains_local_absolute_path(identifier):
        errors.append(f"{relative_path}: $id contains a local absolute path: {identifier!r}")
    if not identifier.startswith(namespaces.base):
        errors.append(
            f"{relative_path}: $id must be below schemas.base {namespaces.base!r}: "
            f"{identifier!r}"
        )

    if relative_path.startswith("examples/eligibility-use-case/schemas/"):
        if not identifier.startswith(namespaces.legacy):
            errors.append(
                f"{relative_path}: eligibility use-case $id must be below "
                f"schemas.legacy {namespaces.legacy!r}"
            )
    elif relative_path.startswith("schemas/modeling/"):
        if not identifier.startswith(namespaces.modeling):
            errors.append(
                f"{relative_path}: modeling contract $id must be below "
                f"schemas.modeling {namespaces.modeling!r}"
            )
    return errors


def audit_schema_identifiers(
    root: Path = ROOT,
    namespace_config: Path | None = None,
    paths: tuple[Path, ...] | None = None,
) -> SchemaAuditResult:
    config_path = namespace_config or root / "config" / "namespaces.yaml"
    namespaces = load_schema_namespaces(config_path)
    schema_paths = paths if paths is not None else tracked_and_intended_schema_files(root)
    errors: list[str] = []
    identifiers: list[str] = []
    seen_identifiers: dict[str, str] = {}
    relative_paths: list[str] = []

    for path in sorted(schema_paths, key=lambda item: item.as_posix()):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = path.as_posix()
        relative_paths.append(relative)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: invalid JSON: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{relative}: JSON Schema root must be an object")
            continue

        meta_schema = data.get("$schema")
        if meta_schema != DRAFT_2020_12:
            errors.append(
                f"{relative}: $schema must equal {DRAFT_2020_12!r}, "
                f"got {meta_schema!r}"
            )
        identifier = data.get("$id")
        errors.extend(_validate_identifier(identifier, relative, namespaces))
        if isinstance(identifier, str) and identifier:
            identifiers.append(identifier)
            previous = seen_identifiers.get(identifier)
            if previous is not None:
                errors.append(
                    f"{relative}: duplicate $id {identifier!r}; first declared in {previous}"
                )
            else:
                seen_identifiers[identifier] = relative

    if not relative_paths:
        errors.append(
            "no tracked or intended *.schema.json files found below schemas/ or examples/"
        )
    return SchemaAuditResult(
        paths=tuple(relative_paths),
        identifiers=tuple(identifiers),
        errors=tuple(errors),
    )


def main() -> int:
    try:
        result = audit_schema_identifiers()
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f"Schema identifier gate configuration error: {exc}")
        return 1

    if result.errors:
        print("Schema identifier gate: FAIL")
        for error in result.errors:
            print(f"- {error}")
        return 1

    print("Schema identifier gate: PASS")
    print(f"- schema files checked: {len(result.paths)}")
    print(f"- unique schema identifiers: {len(result.identifiers)}")
    print("- network access: not used")
    return 0


if __name__ == "__main__":
    sys.exit(main())
