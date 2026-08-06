#!/usr/bin/env python3
"""Reject unapproved legacy ontology and schema identifiers in current assets."""

from __future__ import annotations

import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "legacy-term-allowlist.yaml"
ALLOWED_CATEGORIES = {
    "change_log_generator",
    "deprecated_declaration",
    "deprecated_declaration_generator",
    "migration_source",
    "migration_test",
    "migration_tool",
}
REQUIRED_LEGACY_TERMS = {
    "http://example.org/" + "kg-mnp#",
    "http://example.org/" + "kg-mnp/",
    "https://example.org/" + "kg-mnp/",
    "produces" + "BlockingReason",
    "has" + "Subscription",
    "owns" + "PhoneNumber",
    "related" + "Account",
    "depends" + "On",
    "Assessment" + "Dependency",
}


@dataclass(frozen=True)
class Allowance:
    term: str
    path: str
    line_text: str
    count: int
    category: str
    reason: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.term, self.path, self.line_text)


@dataclass(frozen=True)
class Policy:
    scan_roots: tuple[str, ...]
    terms: tuple[str, ...]
    allowances: tuple[Allowance, ...]


@dataclass(frozen=True)
class Occurrence:
    term: str
    path: str
    line_number: int
    line_text: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.term, self.path, self.line_text)


@dataclass(frozen=True)
class AuditResult:
    occurrences: tuple[Occurrence, ...]
    allowed_counts: Counter[str]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _plain_relative_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    path = PurePosixPath(value.replace("\\", "/"))
    text = path.as_posix()
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must be a repository-relative path: {value!r}")
    if any(char in text for char in "*?[]"):
        raise ValueError(f"{field} must not contain a glob: {value!r}")
    return text


def load_policy(path: Path = DEFAULT_POLICY) -> Policy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("legacy-term policy must be a version: 1 mapping")

    raw_roots = raw.get("scan_roots")
    raw_terms = raw.get("legacy_terms")
    raw_allowances = raw.get("allowed_occurrences", [])
    if not isinstance(raw_roots, list) or not raw_roots:
        raise ValueError("scan_roots must be a non-empty list")
    if not isinstance(raw_terms, list) or not raw_terms:
        raise ValueError("legacy_terms must be a non-empty list")
    if not isinstance(raw_allowances, list):
        raise ValueError("allowed_occurrences must be a list")

    scan_roots = tuple(_plain_relative_path(item, "scan_root") for item in raw_roots)
    if len(scan_roots) != len(set(scan_roots)):
        raise ValueError("scan_roots contains duplicates")

    if any(not isinstance(term, str) or not term for term in raw_terms):
        raise ValueError("every legacy term must be a non-empty string")
    terms = tuple(raw_terms)
    if len(terms) != len(set(terms)):
        raise ValueError("legacy_terms contains duplicates")
    missing_required = sorted(REQUIRED_LEGACY_TERMS - set(terms))
    if missing_required:
        raise ValueError(
            "legacy_terms is missing required Stage 03 token(s): "
            + ", ".join(missing_required)
        )

    allowances: list[Allowance] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw_allowances, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"allowed_occurrences[{index}] must be a mapping")
        term = item.get("term")
        if term not in terms:
            raise ValueError(f"allowed_occurrences[{index}] has unknown term: {term!r}")
        allowed_path = _plain_relative_path(item.get("path"), "allowance path")
        if not any(
            allowed_path == root or allowed_path.startswith(f"{root}/")
            for root in scan_roots
        ):
            raise ValueError(
                f"allowed_occurrences[{index}] path is outside scan_roots: {allowed_path}"
            )
        line_text = item.get("line_text")
        if not isinstance(line_text, str) or not line_text or line_text != line_text.strip():
            raise ValueError(
                f"allowed_occurrences[{index}] line_text must be exact stripped text"
            )
        count = item.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError(f"allowed_occurrences[{index}] count must be a positive integer")
        category = item.get("category")
        if category not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"allowed_occurrences[{index}] has unsupported category: {category!r}"
            )
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"allowed_occurrences[{index}] requires a reason")
        allowance = Allowance(
            term=term,
            path=allowed_path,
            line_text=line_text,
            count=count,
            category=category,
            reason=reason.strip(),
        )
        if allowance.key in seen_keys:
            raise ValueError(
                "duplicate allowance key; combine it into one exact count: "
                f"{allowance.term} in {allowance.path}: {allowance.line_text}"
            )
        seen_keys.add(allowance.key)
        allowances.append(allowance)

    return Policy(scan_roots=scan_roots, terms=terms, allowances=tuple(allowances))


def tracked_and_intended_files(root: Path, scan_roots: tuple[str, ...]) -> tuple[Path, ...]:
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
    # Stage 07 golden N-Quads intentionally copy the frozen Stage 03 TBox.
    # The source ontology release remains scanned; generated package copies
    # are validated by the GraphDB package assembler instead of duplicating
    # every approved deprecated declaration for each scenario.
    excluded_prefix = "examples/graphdb/expected/"
    return tuple(
        root / PurePosixPath(relative)
        for relative in sorted(set(relative_paths))
        if relative
        and not relative.startswith(excluded_prefix)
        and (root / PurePosixPath(relative)).is_file()
    )


def find_occurrences(root: Path, policy: Policy) -> tuple[tuple[Occurrence, ...], tuple[str, ...]]:
    occurrences: list[Occurrence] = []
    errors: list[str] = []
    for path in tracked_and_intended_files(root, policy.scan_roots):
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        if b"\0" in content:
            continue
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            errors.append(f"non-UTF-8 tracked text file: {relative}: {exc}")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            for term in policy.terms:
                for _ in range(line.count(term)):
                    occurrences.append(
                        Occurrence(
                            term=term,
                            path=relative,
                            line_number=line_number,
                            line_text=stripped,
                        )
                    )
    return tuple(occurrences), tuple(errors)


def audit_repository(
    root: Path = ROOT,
    policy_path: Path = DEFAULT_POLICY,
) -> AuditResult:
    policy = load_policy(policy_path)
    occurrences, errors = find_occurrences(root, policy)

    approved = Counter()
    for allowance in policy.allowances:
        approved[allowance.key] = allowance.count
    consumed: Counter[tuple[str, str, str]] = Counter()
    allowed_by_term: Counter[str] = Counter()
    audit_errors = list(errors)

    for occurrence in occurrences:
        if consumed[occurrence.key] < approved[occurrence.key]:
            consumed[occurrence.key] += 1
            allowed_by_term[occurrence.term] += 1
            continue
        audit_errors.append(
            "unapproved legacy identifier "
            f"{occurrence.term!r} at {occurrence.path}:{occurrence.line_number}: "
            f"{occurrence.line_text}"
        )

    for allowance in policy.allowances:
        if allowance.path.startswith("examples/graphdb/expected/"):
            continue
        missing = allowance.count - consumed[allowance.key]
        if missing > 0:
            audit_errors.append(
                "stale or missing approved occurrence "
                f"({missing} of {allowance.count}) for {allowance.term!r} in "
                f"{allowance.path}: {allowance.line_text}"
            )

    return AuditResult(
        occurrences=occurrences,
        allowed_counts=allowed_by_term,
        errors=tuple(audit_errors),
    )


def main() -> int:
    try:
        policy = load_policy()
        result = audit_repository()
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f"Legacy term scan configuration error: {exc}")
        return 1

    if result.errors:
        print("Legacy term scan: FAIL")
        for error in result.errors:
            print(f"- {error}")
        return 1

    print("Legacy term scan: PASS")
    for term in policy.terms:
        print(f"- {term}: {result.allowed_counts[term]} approved historical occurrence(s)")
    print("- unapproved runtime occurrences: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
