"""Project Workspace filesystem confinement checks."""

from __future__ import annotations

from pathlib import Path

from zhigou_toolchain.contracts.errors import PathSecurityError


def validate_workspace_tree(root: Path) -> None:
    resolved_root = root.resolve(strict=True)
    if root.is_symlink():
        raise PathSecurityError("Workspace root must not be a symlink")
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            try:
                path.resolve(strict=True).relative_to(resolved_root)
            except (OSError, ValueError) as exc:
                raise PathSecurityError(f"Workspace symlink escapes root: {relative}") from exc
            raise PathSecurityError(f"Workspace symlinks are forbidden: {relative}")
        if not path.is_dir() and not path.is_file():
            raise PathSecurityError(f"non-regular Workspace entry: {relative}")


def confirmed_authority_files(root: Path) -> tuple[str, ...]:
    confirmed = root / "artifacts" / "confirmed"
    if not confirmed.is_dir():
        return ()
    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(confirmed.rglob("*"))
        if path.is_file()
    )


def validate_confirmed_authority(root: Path, *, domain_packs_root=None) -> None:
    """Accept only core-confirmed packages with a replayable authority closure.

    Arbitrary files in the confirmation directory are still forbidden. The
    historical empty-directory-only guard could never accept a completed
    modeling workflow; this replaces that restriction with semantic checks.
    """
    from zhigou_toolchain.modeling.control_plane.artifacts import (
        artifact_manifest,
        read_json,
    )
    from zhigou_toolchain.modeling.control_plane.confirmation import (
        verify_confirmed_package,
    )
    from zhigou_toolchain.semantic_kernel.input_attestation import attest_compiler_input
    from zhigou_toolchain.semantic_kernel.policy import load_compiler_policy

    confirmed = root / "artifacts" / "confirmed"
    files = list(confirmed.rglob("*"))
    checked = set()
    for path in files:
        if not path.is_file() or path.name != "ontology-confirmed-modeling-package.json":
            continue
        package = read_json(path)
        verify_confirmed_package(package)
        expected = confirmed / "modeling" / package["package_id"].rsplit(":", 1)[-1]
        if path.parent != expected:
            raise ValueError("confirmed package is outside its deterministic location")
        manifest = path.parent / "artifact-manifest.json"
        if read_json(manifest) != artifact_manifest({path.name: path.read_bytes()}):
            raise ValueError("confirmed artifact manifest differs")
        attest_compiler_input(root, package, supported_types=set(load_compiler_policy()["supported_candidate_types"]),
                             domain_packs_root=domain_packs_root)
        checked.update({path, manifest})
    if any(path.is_file() and path not in checked for path in files):
        raise ValueError("unrecognized confirmed authority file")
