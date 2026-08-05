"""Central, offline KG-MNP Modeling CLI for Stage 04."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from .canonical_json import canonical_json_bytes, semantic_hash
from .contracts import CONTRACT_BY_NAME, ContractRegistryError
from .dependencies import (
    DependencyError,
    load_modeling_dependencies,
    verify_ontology_baseline_manifest,
)
from .proposal import generate_modeling_proposal
from .registry import contract_names, validate_contract
from .semantic_validation import (
    SemanticValidationError,
    validate_cleaned_partial_data_semantics,
    validate_mapping_rules_semantics,
    validate_modeling_proposal_semantics,
    validate_proposal_policy_semantics,
    validate_terminology_profile_semantics,
)


class DuplicateKeyError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read JSON input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"contract document root must be an object: {path}")
    return value


def _json_print(payload: Any, *, error: bool = False) -> None:
    options = {"indent": 2, "sort_keys": True}
    text = json.dumps(payload, ensure_ascii=False, **options)
    stream = sys.stderr if error else sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        text = json.dumps(payload, ensure_ascii=True, **options)
    print(text, file=stream)


def _dependency_payload() -> dict[str, Any]:
    values = load_modeling_dependencies()
    baseline = values["ontology_baseline"]
    rules = values["mapping_rules"]
    profile = values["terminology_profile"]
    policy = values["proposal_policy"]
    term_iris = values["term_iris"]
    validate_contract("ontology-baseline-manifest", baseline)
    validate_contract("mapping-rules", rules)
    validate_contract("terminology-profile", profile)
    validate_terminology_profile_semantics(profile, baseline, term_iris=term_iris)
    validate_proposal_policy_semantics(policy)
    validate_mapping_rules_semantics(
        rules,
        baseline,
        profile,
        term_iris=term_iris,
    )
    return values


def cmd_contracts_list() -> int:
    _json_print(
        {
            "contracts": [
                {
                    "name": name,
                    "schema_id": CONTRACT_BY_NAME[name].schema_id,
                    "filename": CONTRACT_BY_NAME[name].filename,
                }
                for name in contract_names()
            ],
            "resolution": "OFFLINE_ONLY",
        }
    )
    return 0


def cmd_contracts_validate(contract: str, input_path: Path) -> int:
    payload = _read_json(input_path)
    validate_contract(contract, payload)
    normalized = contract.replace("_", "-").removesuffix(".schema.json")
    if normalized == "cleaned-partial-data":
        validate_cleaned_partial_data_semantics(payload)
    elif normalized == "modeling-proposal":
        validate_modeling_proposal_semantics(payload)
    _json_print({"contract": normalized, "input": input_path.as_posix(), "valid": True})
    return 0


def cmd_dependencies_verify() -> int:
    dependencies = _dependency_payload()
    baseline = dependencies["ontology_baseline"]
    errors = verify_ontology_baseline_manifest(baseline)
    if errors:
        raise DependencyError("; ".join(errors))
    rules = dependencies["mapping_rules"]
    profile = dependencies["terminology_profile"]
    policy = dependencies["proposal_policy"]
    _json_print(
        {
            "valid": True,
            "network_access": False,
            "ontology_baseline": {
                "id": baseline["baseline_id"],
                "version": baseline["ontology_version"],
                "release_source_hash": baseline["release_source_hash"],
            },
            "mapping_rules": {
                "id": rules["mapping_set_id"],
                "version": rules["mapping_set_version"],
                "semantic_hash": semantic_hash(rules),
            },
            "terminology_profile": {
                "id": profile["profile_id"],
                "version": profile["profile_version"],
                "semantic_hash": semantic_hash(profile),
            },
            "proposal_policy": {
                "version": policy["policy_version"],
                "semantic_hash": semantic_hash(policy),
            },
        }
    )
    return 0


def cmd_propose(input_path: Path, output_path: Path | None, *, force: bool) -> int:
    cleaned = _read_json(input_path)
    dependencies = _dependency_payload()
    proposal = generate_modeling_proposal(
        cleaned,
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        term_iris=set(dependencies["term_iris"]),
    )
    destination = output_path or (
        Path("runtime_outputs") / "modeling" / f"{input_path.stem}.proposal.json"
    )
    if destination.exists() and not force:
        raise FileExistsError(f"output already exists; pass --force to replace it: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical_json_bytes(proposal) + b"\n")
    _json_print(
        {
            "output": destination.as_posix(),
            "proposal_id": proposal["proposal_id"],
            "proposal_semantic_hash": proposal["proposal_semantic_hash"],
            "summary": proposal["summary"],
        }
    )
    return 0


def cmd_proposal_validate(input_path: Path) -> int:
    proposal = _read_json(input_path)
    validate_modeling_proposal_semantics(proposal)
    _json_print(
        {
            "input": input_path.as_posix(),
            "proposal_id": proposal["proposal_id"],
            "valid": True,
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg-mnp",
        description="Deterministic, offline KG-MNP ModelingProposal CLI",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    contracts = subcommands.add_parser("contracts", help="inspect or validate contracts")
    contract_commands = contracts.add_subparsers(dest="contracts_command", required=True)
    contract_commands.add_parser("list", help="list the closed local registry")
    validate = contract_commands.add_parser("validate", help="validate a contract instance")
    validate.add_argument("--contract", required=True, choices=contract_names())
    validate.add_argument("--input", required=True, type=Path)

    dependencies = subcommands.add_parser("dependencies", help="verify frozen dependencies")
    dependency_commands = dependencies.add_subparsers(dest="dependencies_command", required=True)
    dependency_commands.add_parser("verify", help="verify all local dependency hashes")

    propose = subcommands.add_parser("propose", help="generate a review-only proposal")
    propose.add_argument("--input", required=True, type=Path)
    propose.add_argument("--output", type=Path)
    propose.add_argument("--force", action="store_true")

    proposal = subcommands.add_parser("proposal", help="validate a generated proposal")
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    proposal_validate = proposal_commands.add_parser("validate")
    proposal_validate.add_argument("--input", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "contracts" and args.contracts_command == "list":
            return cmd_contracts_list()
        if args.command == "contracts" and args.contracts_command == "validate":
            return cmd_contracts_validate(args.contract, args.input)
        if args.command == "dependencies" and args.dependencies_command == "verify":
            return cmd_dependencies_verify()
        if args.command == "propose":
            return cmd_propose(args.input, args.output, force=args.force)
        if args.command == "proposal" and args.proposal_command == "validate":
            return cmd_proposal_validate(args.input)
    except (
        ContractRegistryError,
        DependencyError,
        DuplicateKeyError,
        FileExistsError,
        OSError,
        SemanticValidationError,
        ValidationError,
        ValueError,
    ) as exc:
        _json_print({"error": type(exc).__name__, "message": str(exc)}, error=True)
        return 1
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
