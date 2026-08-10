"""Central, offline KG-MNP Modeling CLI for Stage 04–05."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from .canonical_json import canonical_json_bytes, semantic_hash
from .confirmation import PackageBuildError, build_confirmed_modeling_package
from .contracts import CONTRACT_BY_NAME, ContractRegistryError
from .dependencies import (
    DependencyError,
    load_modeling_dependencies,
    verify_ontology_baseline_manifest,
)
from .package_validation import load_term_type_index
from .proposal import generate_modeling_proposal
from .registry import contract_names, validate_contract
from .review_log import (
    finalize_review_decision_log,
    init_review_decision_log,
    record_review_action,
    review_status,
)
from .review_policy import ReviewPolicyError, load_default_review_policy, review_policy_hash
from .semantic_validation import (
    SemanticValidationError,
    validate_cleaned_partial_data_semantics,
    validate_confirmed_modeling_package_semantics,
    validate_mapping_rules_semantics,
    validate_modeling_proposal_semantics,
    validate_proposal_policy_semantics,
    validate_review_decision_log_semantics,
    validate_terminology_profile_semantics,
)
from ..compilation.artifacts import ArtifactWriteError, write_artifact_set
from ..compilation.compiler import CompilationError, build_artifact_set
from ..compilation.contracts import CompilationContractError
from ..compilation.policy import CompilerPolicyError, load_compiler_policy
from ..compilation.validator import (
    CompilationValidationError,
    validate_compilation_package_against_authorities,
)
from ..graphdb.cli import add_graphdb_parser, dispatch_graphdb
from ..publication.cli import add_publication_parser, dispatch_publication
from ..webvowl.cli import add_webvowl_parser, dispatch_webvowl


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


def _write_json(path: Path, payload: MappingLike, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"output already exists; pass --force to replace it: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload) + b"\n")


MappingLike = dict[str, Any]


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
    values["review_policy"] = load_default_review_policy()
    values["term_types"] = load_term_type_index()
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
    elif normalized == "review-policy":
        from .review_policy import validate_review_policy_semantics

        validate_review_policy_semantics(payload)
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
    review_policy = dependencies["review_policy"]
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
            "review_policy": {
                "id": review_policy["policy_id"],
                "version": review_policy["policy_version"],
                "semantic_hash": review_policy_hash(review_policy),
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
    _write_json(destination, proposal, force=force)
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


def cmd_review_init(
    *,
    proposal_path: Path,
    reviewer_id: str,
    display_name: str,
    role: str,
    started_at: str,
    output_path: Path | None,
    session_id: str | None,
    affiliation: str | None,
    force: bool,
) -> int:
    proposal = _read_json(proposal_path)
    validate_modeling_proposal_semantics(proposal)
    draft = init_review_decision_log(
        proposal,
        reviewer_id=reviewer_id,
        display_name=display_name,
        role=role,
        started_at=started_at,
        session_label=session_id,
        affiliation=affiliation,
    )
    destination = output_path or Path("runtime_outputs") / "review" / "review-log.draft.json"
    _write_json(destination, draft, force=force)
    _json_print(
        {
            "output": destination.as_posix(),
            "decision_log_id": draft["decision_log_id"],
            "session_id": draft["review_session"]["session_id"],
            "decisions": [],
            "auto_decisions": False,
        }
    )
    return 0


def cmd_review_status(*, proposal_path: Path, decision_log_path: Path) -> int:
    proposal = _read_json(proposal_path)
    decision_log = _read_json(decision_log_path)
    status = review_status(proposal, decision_log)
    _json_print(
        {
            "proposal_id": proposal.get("proposal_id"),
            "decision_log_id": decision_log.get("decision_log_id"),
            **status,
        }
    )
    return 0


def cmd_review_record(
    *,
    proposal_path: Path,
    decision_log_path: Path,
    action_path: Path,
    output_path: Path | None,
    force: bool,
) -> int:
    proposal = _read_json(proposal_path)
    decision_log = _read_json(decision_log_path)
    action = _read_json(action_path)
    dependencies = _dependency_payload()
    next_log = record_review_action(
        proposal,
        decision_log,
        action,
        review_policy=dependencies["review_policy"],
        term_types=dependencies["term_types"],
    )
    destination = output_path or Path("runtime_outputs") / "review" / "review-log.next.json"
    _write_json(destination, next_log, force=force)
    _json_print(
        {
            "output": destination.as_posix(),
            "decision_count": len(next_log["decisions"]),
            "decision_log_id": next_log["decision_log_id"],
            "log_hash": next_log["log_hash"],
        }
    )
    return 0


def cmd_review_validate(*, proposal_path: Path, decision_log_path: Path) -> int:
    proposal = _read_json(proposal_path)
    decision_log = _read_json(decision_log_path)
    dependencies = _dependency_payload()
    require_final = bool(decision_log.get("review_session", {}).get("completed_at"))
    validate_review_decision_log_semantics(
        decision_log,
        proposal,
        review_policy=dependencies["review_policy"],
        require_final=require_final,
        term_types=dependencies["term_types"],
    )
    _json_print(
        {
            "proposal_id": proposal.get("proposal_id"),
            "decision_log_id": decision_log.get("decision_log_id"),
            "valid": True,
            "final": require_final,
        }
    )
    return 0


def cmd_review_finalize(
    *,
    proposal_path: Path,
    decision_log_path: Path,
    completed_at: str,
    output_path: Path | None,
    force: bool,
    input_path: Path | None = None,
) -> int:
    proposal = _read_json(proposal_path)
    decision_log = _read_json(decision_log_path)
    dependencies = _dependency_payload()
    cleaned = _read_json(input_path) if input_path is not None else None
    final_log = finalize_review_decision_log(
        proposal,
        decision_log,
        completed_at=completed_at,
        review_policy=dependencies["review_policy"],
        term_types=dependencies["term_types"],
        cleaned_partial_data=cleaned,
        ontology_baseline=dependencies["ontology_baseline"],
        mapping_rules=dependencies["mapping_rules"],
    )
    destination = output_path or Path("runtime_outputs") / "review" / "review-log.final.json"
    _write_json(destination, final_log, force=force)
    _json_print(
        {
            "output": destination.as_posix(),
            "decision_log_id": final_log["decision_log_id"],
            "log_hash": final_log["log_hash"],
            "decision_count": len(final_log["decisions"]),
            "completed_at": final_log["review_session"]["completed_at"],
        }
    )
    return 0


def cmd_confirm_build(
    *,
    input_path: Path,
    proposal_path: Path,
    decision_log_path: Path,
    output_path: Path | None,
    allow_blocked: bool,
    force: bool,
) -> int:
    cleaned = _read_json(input_path)
    proposal = _read_json(proposal_path)
    decision_log = _read_json(decision_log_path)
    dependencies = _dependency_payload()
    package = build_confirmed_modeling_package(
        cleaned,
        proposal,
        decision_log,
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        dependencies["review_policy"],
        allow_blocked=allow_blocked,
        term_types=dependencies["term_types"],
    )
    destination = output_path or (
        Path("runtime_outputs")
        / "confirmed-packages"
        / f"{input_path.stem}.package.json"
    )
    _write_json(destination, package, force=force)
    manifest = package["publication_manifest"]
    _json_print(
        {
            "output": destination.as_posix(),
            "package_id": package["package_id"],
            "package_semantic_hash": package["package_semantic_hash"],
            "package_status": manifest["package_status"],
            "compile_allowed": manifest["compile_allowed"],
            "confirmed_abox_count": manifest["confirmed_abox_count"],
            "confirmed_schema_delta_count": manifest["confirmed_schema_delta_count"],
            "rejected_item_count": manifest["rejected_item_count"],
            "deferred_item_count": manifest["deferred_item_count"],
        }
    )
    return 0


def cmd_package_validate(
    *,
    input_path: Path,
    proposal_path: Path,
    decision_log_path: Path,
    package_path: Path,
) -> int:
    cleaned = _read_json(input_path)
    proposal = _read_json(proposal_path)
    decision_log = _read_json(decision_log_path)
    package = _read_json(package_path)
    dependencies = _dependency_payload()
    validate_confirmed_modeling_package_semantics(
        package,
        proposal,
        decision_log,
        cleaned_partial_data=cleaned,
        ontology_baseline=dependencies["ontology_baseline"],
        mapping_rules=dependencies["mapping_rules"],
        terminology_profile=dependencies["terminology_profile"],
        proposal_policy=dependencies["proposal_policy"],
        review_policy=dependencies["review_policy"],
        term_types=dependencies["term_types"],
        require_complete=True,
    )
    _json_print(
        {
            "valid": True,
            "deterministic_reconstruction_match": True,
            "package_id": package.get("package_id"),
            "package_status": package.get("publication_manifest", {}).get("package_status"),
            "compile_allowed": package.get("publication_manifest", {}).get("compile_allowed"),
        }
    )
    return 0


def cmd_package_inspect(*, package_path: Path) -> int:
    package = _read_json(package_path)
    manifest = package.get("publication_manifest", {})
    _json_print(
        {
            "package_id": package.get("package_id"),
            "package_semantic_hash": package.get("package_semantic_hash"),
            "source_proposal_id": package.get("source_proposal_id"),
            "review_decision_log_id": package.get("review_decision_log_id"),
            "confirmed_abox_count": len(package.get("confirmed_abox_decisions", [])),
            "confirmed_schema_delta_count": len(package.get("confirmed_schema_delta", [])),
            "rejected_item_count": len(package.get("rejected_items", [])),
            "deferred_item_count": len(package.get("deferred_items", [])),
            "publication_manifest": manifest,
        }
    )
    return 0


def _compilation_authorities(
    input_path: Path,
    proposal_path: Path,
    decision_log_path: Path,
    package_path: Path,
) -> tuple[dict[str, Any], ...]:
    dependencies = _dependency_payload()
    return (
        _read_json(input_path),
        _read_json(proposal_path),
        _read_json(decision_log_path),
        _read_json(package_path),
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
        dependencies["review_policy"],
    )


def cmd_compile_build(
    *,
    input_path: Path,
    proposal_path: Path,
    decision_log_path: Path,
    package_path: Path,
    output_dir: Path | None,
    force: bool,
) -> int:
    authorities = _compilation_authorities(
        input_path, proposal_path, decision_log_path, package_path
    )
    policy = load_compiler_policy()
    files, manifest = build_artifact_set(*authorities, policy)
    destination = output_dir or (
        Path("runtime_outputs")
        / "compilation"
        / str(manifest["compilation_id"]).rsplit(":", 1)[-1]
    )
    write_artifact_set(destination, files, force=force)
    _json_print(
        {
            "output": destination.as_posix(),
            "compilation_id": manifest["compilation_id"],
            "compilation_semantic_hash": manifest["compilation_semantic_hash"],
            "source_package_id": manifest["source_package_id"],
            "asserted_fact_count": manifest["asserted_fact_count"],
            "shacl_status": manifest["shacl_status"],
            "owl_consistency_status": manifest["owl_consistency_status"],
            "release_status": manifest["release_status"],
        }
    )
    return 0


def cmd_compile_validate(
    *,
    input_path: Path,
    proposal_path: Path,
    decision_log_path: Path,
    package_path: Path,
    compilation_dir: Path,
) -> int:
    authorities = _compilation_authorities(
        input_path, proposal_path, decision_log_path, package_path
    )
    result = validate_compilation_package_against_authorities(
        compilation_dir, *authorities, load_compiler_policy()
    )
    _json_print(result)
    return 0


def cmd_compile_inspect(*, compilation_dir: Path) -> int:
    manifest_path = compilation_dir / "compilation-manifest.json"
    manifest = _read_json(manifest_path)
    _json_print(
        {
            "inspection_only": True,
            "validated": False,
            "notice": "inspect is not validation",
            "compilation_id": manifest.get("compilation_id"),
            "source_package_id": manifest.get("source_package_id"),
            "release_status_claim": manifest.get("release_status"),
            "shacl_status_claim": manifest.get("shacl_status"),
            "owl_consistency_status_claim": manifest.get("owl_consistency_status"),
            "artifact_count": len(manifest.get("artifact_manifest", [])),
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kg-mnp",
        description="Deterministic, offline KG-MNP modeling and human-review CLI",
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

    review = subcommands.add_parser("review", help="explicit human review workflow")
    review_commands = review.add_subparsers(dest="review_command", required=True)

    review_init = review_commands.add_parser("init", help="create an empty draft decision log")
    review_init.add_argument("--proposal", required=True, type=Path)
    review_init.add_argument("--reviewer-id", required=True)
    review_init.add_argument("--display-name", required=True)
    review_init.add_argument("--role", required=True)
    review_init.add_argument("--started-at", required=True)
    review_init.add_argument("--session-id", help="optional stable session label")
    review_init.add_argument("--affiliation")
    review_init.add_argument("--output", type=Path)
    review_init.add_argument("--force", action="store_true")

    review_status_cmd = review_commands.add_parser("status", help="inspect coverage; no writes")
    review_status_cmd.add_argument("--proposal", required=True, type=Path)
    review_status_cmd.add_argument("--decision-log", required=True, type=Path)

    review_record = review_commands.add_parser("record", help="append one explicit review action")
    review_record.add_argument("--proposal", required=True, type=Path)
    review_record.add_argument("--decision-log", required=True, type=Path)
    review_record.add_argument("--action", required=True, type=Path)
    review_record.add_argument("--output", type=Path)
    review_record.add_argument("--force", action="store_true")

    review_validate = review_commands.add_parser("validate", help="validate a decision log")
    review_validate.add_argument("--proposal", required=True, type=Path)
    review_validate.add_argument("--decision-log", required=True, type=Path)

    review_finalize = review_commands.add_parser("finalize", help="finalize a complete decision log")
    review_finalize.add_argument("--proposal", required=True, type=Path)
    review_finalize.add_argument("--decision-log", required=True, type=Path)
    review_finalize.add_argument("--completed-at", required=True)
    review_finalize.add_argument(
        "--input",
        type=Path,
        help="optional CleanedPartialData for finalize-time input checks",
    )
    review_finalize.add_argument("--output", type=Path)
    review_finalize.add_argument("--force", action="store_true")

    confirm = subcommands.add_parser("confirm", help="build a confirmed modeling package")
    confirm_commands = confirm.add_subparsers(dest="confirm_command", required=True)
    confirm_build = confirm_commands.add_parser("build", help="build package from final log")
    confirm_build.add_argument("--input", required=True, type=Path)
    confirm_build.add_argument("--proposal", required=True, type=Path)
    confirm_build.add_argument("--decision-log", required=True, type=Path)
    confirm_build.add_argument("--output", type=Path)
    confirm_build.add_argument("--allow-blocked", action="store_true")
    confirm_build.add_argument("--force", action="store_true")

    package = subcommands.add_parser("package", help="inspect or validate confirmed packages")
    package_commands = package.add_subparsers(dest="package_command", required=True)
    package_validate = package_commands.add_parser("validate")
    package_validate.add_argument("--input", required=True, type=Path)
    package_validate.add_argument("--proposal", required=True, type=Path)
    package_validate.add_argument("--decision-log", required=True, type=Path)
    package_validate.add_argument("--package", required=True, type=Path)
    package_inspect = package_commands.add_parser("inspect")
    package_inspect.add_argument("--package", required=True, type=Path)

    compile_cmd = subcommands.add_parser(
        "compile", help="build or validate formal Stage 06 semantic artifacts"
    )
    compile_commands = compile_cmd.add_subparsers(dest="compile_command", required=True)
    compile_build = compile_commands.add_parser("build", help="compile a READY confirmed package")
    compile_build.add_argument("--input", required=True, type=Path)
    compile_build.add_argument("--proposal", required=True, type=Path)
    compile_build.add_argument("--decision-log", required=True, type=Path)
    compile_build.add_argument("--package", required=True, type=Path)
    compile_build.add_argument("--output-dir", type=Path)
    compile_build.add_argument("--force", action="store_true")
    compile_validate = compile_commands.add_parser(
        "validate", help="rebuild from authorities and compare all artifacts"
    )
    compile_validate.add_argument("--input", required=True, type=Path)
    compile_validate.add_argument("--proposal", required=True, type=Path)
    compile_validate.add_argument("--decision-log", required=True, type=Path)
    compile_validate.add_argument("--package", required=True, type=Path)
    compile_validate.add_argument("--compilation-dir", required=True, type=Path)
    compile_inspect = compile_commands.add_parser(
        "inspect", help="read a manifest summary without validating it"
    )
    compile_inspect.add_argument("--compilation-dir", required=True, type=Path)
    add_graphdb_parser(subcommands)
    add_webvowl_parser(subcommands)
    add_publication_parser(subcommands)
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
        if args.command == "review" and args.review_command == "init":
            return cmd_review_init(
                proposal_path=args.proposal,
                reviewer_id=args.reviewer_id,
                display_name=args.display_name,
                role=args.role,
                started_at=args.started_at,
                output_path=args.output,
                session_id=args.session_id,
                affiliation=args.affiliation,
                force=args.force,
            )
        if args.command == "review" and args.review_command == "status":
            return cmd_review_status(
                proposal_path=args.proposal,
                decision_log_path=args.decision_log,
            )
        if args.command == "review" and args.review_command == "record":
            return cmd_review_record(
                proposal_path=args.proposal,
                decision_log_path=args.decision_log,
                action_path=args.action,
                output_path=args.output,
                force=args.force,
            )
        if args.command == "review" and args.review_command == "validate":
            return cmd_review_validate(
                proposal_path=args.proposal,
                decision_log_path=args.decision_log,
            )
        if args.command == "review" and args.review_command == "finalize":
            return cmd_review_finalize(
                proposal_path=args.proposal,
                decision_log_path=args.decision_log,
                completed_at=args.completed_at,
                output_path=args.output,
                force=args.force,
                input_path=getattr(args, "input", None),
            )
        if args.command == "confirm" and args.confirm_command == "build":
            return cmd_confirm_build(
                input_path=args.input,
                proposal_path=args.proposal,
                decision_log_path=args.decision_log,
                output_path=args.output,
                allow_blocked=args.allow_blocked,
                force=args.force,
            )
        if args.command == "package" and args.package_command == "validate":
            return cmd_package_validate(
                input_path=args.input,
                proposal_path=args.proposal,
                decision_log_path=args.decision_log,
                package_path=args.package,
            )
        if args.command == "package" and args.package_command == "inspect":
            return cmd_package_inspect(package_path=args.package)
        if args.command == "compile" and args.compile_command == "build":
            return cmd_compile_build(
                input_path=args.input,
                proposal_path=args.proposal,
                decision_log_path=args.decision_log,
                package_path=args.package,
                output_dir=args.output_dir,
                force=args.force,
            )
        if args.command == "compile" and args.compile_command == "validate":
            return cmd_compile_validate(
                input_path=args.input,
                proposal_path=args.proposal,
                decision_log_path=args.decision_log,
                package_path=args.package,
                compilation_dir=args.compilation_dir,
            )
        if args.command == "compile" and args.compile_command == "inspect":
            return cmd_compile_inspect(compilation_dir=args.compilation_dir)
        if args.command == "graphdb":
            return dispatch_graphdb(args, _json_print)
        if args.command == "webvowl":
            return dispatch_webvowl(args)
        if args.command == "publication":
            return dispatch_publication(args)
    except (
        ArtifactWriteError,
        CompilationContractError,
        CompilationError,
        CompilationValidationError,
        CompilerPolicyError,
        ContractRegistryError,
        DependencyError,
        DuplicateKeyError,
        FileExistsError,
        OSError,
        PackageBuildError,
        ReviewPolicyError,
        RuntimeError,
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
