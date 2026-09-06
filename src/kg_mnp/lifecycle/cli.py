"""Fail-closed CLI for the Prompt 6 lifecycle surface."""
from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

from .changes import (
    attach_candidate_package,
    create_change_proposal,
    evaluate_change,
    list_change_proposals,
    submit_change_proposal,
)
from .consumer import list_consumers, register_consumer, verify_consumer
from .diff import check_version, create_diff, verify_diff
from .environment import (
    activate,
    execute_activation,
    init_environment,
    list_environments,
    propose_activation,
    review_activation,
    rollback,
)
from .errors import LifecycleError
from .feedback import add_feedback, inspect_feedback, list_feedback
from .impact import analyze_impact, build_dependency_graph
from .registry.events import read_events
from .registry.import_package import import_package
from .registry.index import rebuild_indexes
from .registry.manifest import init_registry
from .registry.replay import replay
from .registry.snapshot import rebuild_snapshot
from .registry.verifier import verify_registry
from .regression import plan_regression, run_regression
from .release import (
    attest_release,
    create_release_candidate,
    list_releases,
    publish_release,
    record_review,
)
from .store import list_records

# These options are deliberately rejected rather than ignored.  Ignoring one
# would turn a typo or an attempted bypass into an apparently successful
# lifecycle operation.
_FORBIDDEN_FLAGS = {
    "--force", "--auto-approve", "--auto-release", "--auto-activate",
    "--auto-rollback", "--auto-version", "--auto-bump", "--skip-diff",
    "--skip-impact", "--skip-regression", "--ignore-breaking",
    "--ignore-security", "--waive-required", "--accept-timeout",
    "--skip-consumer", "--skip-package-verify",
}

_ACTION_WORDS = {
    "init", "status", "verify", "snapshot", "rebuild-index", "indexes",
    "events", "head", "import-package", "list-packages", "packages",
    "inspect-package", "verify-package", "add", "record", "import", "list",
    "inspect", "create", "submit", "attach-package", "evaluate", "graph",
    "dependency-graph", "analyze", "plan", "inspect-plan", "run", "candidate",
    "create-candidate", "review", "approve", "decide", "finalize", "publish",
    "release", "attest", "environment", "pointer", "history", "activate",
    "rollback", "propose", "execute", "version-check",
}

_OPTION_ALIASES = {
    "--registry-name": "--name",
    "--base-package": "--base",
    "--candidate-package": "--candidate",
    "--diff": "--diff-file",
    "--environment": "--environment-id",
    "--release": "--release-id",
    "--candidate": "--candidate-id",
    "--review": "--review-id",
    "--change": "--change-proposal-id",
    "--evaluation": "--change-evaluation-id",
    "--base-release": "--base-release-id",
    "--impact": "--impact-id",
    "--role": "--roles",
    "--action": "--decision",
    "--proposal": "--proposal-id",
}


def _normalise_args(args: list[str]) -> list[str]:
    """Accept the documented positional CLI form and the compact form.

    The original Foundation commands use options for paths while the lifecycle
    contract intentionally documents ``<workspace>`` positionally.  Keeping a
    small normalisation layer lets both forms share one fail-closed dispatcher.
    """
    if not args:
        return args
    domain = args[0]
    nested = args[1:4]
    consumed: set[int] = set()
    option_names = set(_OPTION_ALIASES) | {
        "--registry", "--workspace", "--name", "--project-id", "--ontology-iris",
        "--package-names", "--package", "--type", "--package-id", "--package-name",
        "--reported-by", "--severity", "--observations", "--id", "--base",
        "--candidate", "--base-version", "--candidate-version", "--classification",
        "--file", "--owner", "--term-iris", "--diff-file", "--plan-file",
        "--candidate-id", "--base-package-id", "--candidate-package-id", "--diff-id",
        "--regression-id", "--reviewer-id", "--roles", "--decision", "--rationale",
        "--package-version", "--class", "--environment-id", "--release-id",
        "--base-release-id",
        "--created-by", "--expected-registry-head", "--expected-generation",
        "--expected-pointer-hash", "--change-proposal-id", "--change-evaluation-id",
        "--impact-id", "--ontology-iri", "--outcomes", "--scope",
        "--action", "--feedback-id", "--consumer-id", "--plan-id", "--report-id",
        "--version-report-id", "--package-lock-id", "--package-archive-sha256",
        "--proposal-id", "--decision-id", "--requested-by",
    }
    # Identify a positional workspace.  Values following an option are never
    # considered paths (important for Windows paths and JSON filenames).
    workspace_index: int | None = None
    for i, token in enumerate(args[1:], 1):
        if i - 1 in consumed:
            continue
        if token.startswith("-"):
            if token in option_names and i + 1 < len(args):
                consumed.add(i)
                consumed.add(i + 1)
            continue
        if i and args[i - 1].startswith("-"):
            continue
        if token in _ACTION_WORDS or token in {domain, "lifecycle"}:
            continue
        workspace_index = i
        break
    out = list(args)
    if workspace_index is not None:
        workspace = out.pop(workspace_index)
        if "--registry" not in out and "--workspace" not in out:
            out.extend(["--registry", workspace])
        # Positional identifiers after the workspace are mapped to the stable
        # option names consumed by the dispatcher.
        positional = [
            token for i, token in enumerate(args[workspace_index + 1:], workspace_index + 1)
            if not token.startswith("-") and token not in _ACTION_WORDS
            and not (i > 0 and args[i - 1].startswith("-"))
        ]
        if positional:
            if domain == "registry" and args[1] in {"inspect-package", "verify-package"}:
                out.extend(["--package", positional[0]])
            elif domain == "feedback" and args[1] == "inspect":
                out.extend(["--feedback-id", positional[0]])
            elif domain == "change" and args[1] in {"submit", "inspect", "status", "evaluate"}:
                out.extend(["--id", positional[0]])
            elif domain == "consumer" and args[1] in {"inspect", "verify"}:
                out.extend(["--consumer-id", positional[0]])
            elif domain == "regression" and args[1] in {"inspect-plan", "inspect", "verify", "run"}:
                out.extend(["--plan-id" if args[1] == "inspect-plan" else "--report-id", positional[0]])
            elif domain == "release":
                if "candidate" in nested and args[2] in {"inspect", "submit"}:
                    out.extend(["--candidate-id", positional[0]])
                elif "review" in nested and args[2] in {"status", "finalize", "decide"}:
                    out.extend(["--review-id", positional[0]])
            elif domain == "environment" and args[1] in {"status", "history", "pointer"}:
                out.extend(["--environment-id", positional[0]])
    # Rename documented aliases after extracting positional values.
    return [_OPTION_ALIASES.get(token, token) for token in out]


def _jsonable(v): return v


def _emit(command: str, result: Any, *, code: int = 0, status: str = "PASS", errors: list[str] | None = None, warnings: list[str] | None = None, as_json: bool = True) -> int:
    subject = None
    if isinstance(result, dict):
        subject = next((result.get(key) for key in (
            "id", "registry_id", "package_id", "feedback_id", "change_proposal_id",
            "consumer_id", "diff_id", "impact_id", "test_plan_id", "report_id",
            "release_candidate_id", "review_id", "release_id", "environment_id",
            "execution_id", "attestation_id",
        ) if result.get(key) is not None), None)
    envelope={"command":command,"status":status,"code":code,"subject":subject,"errors":errors or [],"warnings":warnings or [],"result":result}
    if as_json: print(json.dumps(envelope,ensure_ascii=False,sort_keys=True,indent=2))
    elif isinstance(result,(dict,list)): print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    else: print(result)
    return code

def _arg(args: list[str], name: str, default=None):
    try: return args[args.index(name)+1]
    except (ValueError,IndexError): return default
def _args(args: list[str], name: str):
    value=_arg(args,name,""); return [x for x in value.split(",") if x] if value is not None else []
def _path(args): return Path(_arg(args,"--registry", _arg(args,"--workspace", "registry")))
def _required(args,name):
    value=_arg(args,name)
    if value is None: raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", f"missing required option {name}")
    return value


def _required_any(args, *names):
    for name in names:
        value = _arg(args, name)
        if value is not None:
            return value
    raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", f"missing required option {'/'.join(names)}")

def dispatch(args: list[str]):
    if not args or args[0] in {"-h","--help"}: return {"help":"kg-mnp lifecycle <registry|feedback|change|diff|consumer|impact|regression|release|environment|activate|rollback>"}
    domain, action = args[0], args[1] if len(args)>1 else "status"; subaction = args[2] if len(args)>2 else None; root=_path(args)
    if domain=="registry":
        if action=="init": return init_registry(root, registry_name=_arg(args,"--name","local"), project_id=_arg(args,"--project-id","project"), created_by=_arg(args,"--created-by","operator"), accepted_ontology_iris=_args(args,"--ontology-iris"), accepted_package_names=_args(args,"--package-names"))
        if action in {"status","verify"}: return verify_registry(root)
        if action=="head": return json.loads((root/"state/registry-head.json").read_bytes())
        if action=="events": return read_events(root)
        if action=="snapshot": return rebuild_snapshot(root)
        if action in {"rebuild-index","indexes"}: return rebuild_indexes(root)
        if action in {"list-packages","packages"}: return replay(root).get("packages",[])
        if action=="import-package": return import_package(root,_required(args,"--package"))
        if action in {"verify-package","inspect-package"}:
            package_id = _required(args,"--package")
            rows = replay(root).get("packages", [])
            row = next((item for item in rows if item.get("package_id") == package_id or item.get("record_id") == package_id), None)
            if row is None: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "package record not found")
            return {"status":"VERIFIED","package":row} if action == "verify-package" else row
    if domain=="feedback":
        if action in {"add","record"}:
            if _arg(args,"--file"):
                payload=json.loads(Path(_arg(args,"--file")).read_bytes())
                return add_feedback(root, feedback_type=payload["feedback_type"], target_package_id=payload["target_package_id"], observations=payload.get("observations",[]), severity=payload.get("severity","INFO"), reported_by=payload.get("reported_by","operator"), source_type=payload.get("source_type","HUMAN"))
            return add_feedback(root,feedback_type=_required(args,"--type"),target_package_id=_required(args,"--package-id"),observations=_args(args,"--observations"),severity=_arg(args,"--severity","INFO"),reported_by=_arg(args,"--reported-by","operator"))
        if action=="import":
            payload=json.loads(Path(_required(args,"--file")).read_bytes())
            rows=payload if isinstance(payload,list) else payload.get("records",[payload])
            return [add_feedback(root, feedback_type=row["feedback_type"], target_package_id=row["target_package_id"], observations=row.get("observations",[]), severity=row.get("severity","INFO"), reported_by=row.get("reported_by","operator")) for row in rows]
        if action=="list": return list_feedback(root)
        if action=="inspect": return inspect_feedback(root,_required(args,"--feedback-id"))
    if domain=="change":
        if action in {"init","create"}:
            base_release_id = _arg(args,"--base-release-id")
            base_package_id = _arg(args,"--base-package-id") or _arg(args,"--base")
            if base_package_id is None and base_release_id is None:
                raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", "a base package or base release is required")
            return create_change_proposal(root,base_package_id=base_package_id,base_release_id=base_release_id,change_type=_arg(args,"--type","CORRECTIVE"),change_scope=_arg(args,"--scope","TBOX"),affected_iris=_args(args,"--affected-iris"),requested_outcomes=_args(args,"--outcomes"))
        if action=="submit": return submit_change_proposal(root,_required(args,"--id"))
        if action=="attach-package": return attach_candidate_package(root,_required(args,"--id"),_required_any(args,"--candidate-package-id","--candidate"))
        if action=="evaluate": return evaluate_change(root,_required(args,"--id"),candidate_package_id=_arg(args,"--candidate-package-id") or _arg(args,"--candidate"),semantic_diff_id=_arg(args,"--diff-id"),version_compatibility_report_id=_arg(args,"--version-report-id"),impact_analysis_id=_arg(args,"--impact-id"),regression_test_report_id=_arg(args,"--regression-id"))
        if action in {"inspect","status"}:
            row = next((x for x in list_change_proposals(root) if x.get("change_proposal_id")==_required(args,"--id")), None)
            if row is None: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "change proposal not found")
            return row
        if action=="list": return list_change_proposals(root)
    if domain=="diff":
        if action in {"create","run"}: return create_diff(_required(args,"--base"),_required(args,"--candidate"),base_version=_arg(args,"--base-version","0.0.0"),candidate_version=_arg(args,"--candidate-version","0.0.0"))
        if action=="verify": return verify_diff(json.loads(Path(_required(args,"--file")).read_bytes()))
        if action=="version-check": return check_version(_required(args,"--base-version"),_required(args,"--candidate-version"),_required(args,"--classification"))
    if domain=="consumer":
        if action in {"register","create"}:
            if _arg(args,"--file"):
                payload=json.loads(Path(_arg(args,"--file")).read_bytes())
                return register_consumer(root, consumer_name=payload["consumer_name"], ontology_iri=payload["ontology_iri"], owner_label=payload.get("owner_label","owner"), required_term_iris=payload.get("required_term_iris",[]), **{k:v for k,v in payload.items() if k not in {"consumer_name","ontology_iri","owner_label","required_term_iris"}})
            return register_consumer(root,consumer_name=_required(args,"--name"),ontology_iri=_required(args,"--ontology-iri"),owner_label=_arg(args,"--owner","owner"),required_term_iris=_args(args,"--term-iris"))
        if action=="list": return list_consumers(root)
        if action in {"inspect","verify"}:
            row = next((x for x in list_consumers(root) if x.get("consumer_id")==_required(args,"--consumer-id")), None)
            if row is None: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "consumer manifest not found")
            return verify_consumer(row) if action == "verify" else row
    if domain=="impact":
        if action in {"graph","dependency-graph"}: return build_dependency_graph(root)
        if action=="analyze": return analyze_impact(root,semantic_diff=json.loads(Path(_required(args,"--diff-file")).read_bytes()))
    if domain=="regression":
        if action in {"plan","create"}: return plan_regression(root,base_package_id=_required_any(args,"--base-package-id","--base"),candidate_package_id=_required_any(args,"--candidate-package-id","--candidate"),semantic_diff_id=_arg(args,"--diff-id",""),impact_analysis_id=_arg(args,"--impact-id",""))
        if action=="run": return run_regression(root,json.loads(Path(_required(args,"--plan-file")).read_bytes()))
        if action in {"inspect-plan","inspect","verify"}:
            folder="records/regressions"; wanted=_required(args,"--plan-id" if action=="inspect-plan" else "--report-id")
            rows=list_records(root,folder); key="test_plan_id" if action=="inspect-plan" else "report_id"
            row=next((x for x in rows if x.get(key)==wanted),None)
            if row is None: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "regression artifact not found")
            return {"status":"VALID","artifact":row} if action=="verify" else row
    if domain=="release":
        if action == "candidate" and subaction in {"inspect", "submit"}:
            candidate_id = _required(args, "--candidate-id")
            row = next((x for x in list_records(root, "records/release-candidates") if x.get("release_candidate_id") == candidate_id), None)
            if row is None: raise LifecycleError("RELEASE_CANDIDATE_INVALID", "release candidate not found")
            if subaction == "submit":
                row = {**row, "candidate_status": "SUBMITTED"}
                from .store import save
                save(root, f"records/release-candidates/{candidate_id.rsplit(':',1)[1]}.json", row)
            return row
        if action == "review" and subaction in {"status", "finalize"}:
            review_id = _required(args, "--review-id")
            row = next((x for x in list_records(root, "records/release-reviews") if x.get("review_id") == review_id), None)
            if row is None: raise LifecycleError("RELEASE_REVIEW_INCOMPLETE", "release review not found")
            if subaction == "finalize" and not row.get("quorum_satisfied"):
                raise LifecycleError("RELEASE_REVIEW_INCOMPLETE", "review quorum is not satisfied")
            return row
        if action in {"candidate","create-candidate"}:
            # ``release candidate create`` normalises to this action.
            return create_release_candidate(root,candidate_package_id=_required_any(args,"--candidate-package-id","--candidate"),base_package_id=_arg(args,"--base-package-id") or _arg(args,"--base"),semantic_diff_id=_arg(args,"--diff-id",""),regression_test_report_id=_arg(args,"--regression-id",""),change_proposal_id=_arg(args,"--change-proposal-id",""),change_evaluation_id=_arg(args,"--change-evaluation-id",""))
        if action in {"review","approve"}:
            target = _arg(args,"--candidate-id")
            if target is None and _arg(args,"--review-id"):
                target = next((x.get("release_candidate_id") for x in list_records(root,"records/release-reviews") if x.get("review_id")==_arg(args,"--review-id")), None)
            return record_review(root, target or _required(args,"--review-id"), reviewer_id=_arg(args,"--reviewer-id","operator"), reviewer_roles=_args(args,"--roles") or ["RELEASE_MANAGER"], action=_arg(args,"--decision","APPROVE"), rationale=_arg(args,"--rationale",""), explicit_human_action=True)
        if action in {"publish","release"}:
            candidate_id = _required(args,"--candidate-id")
            candidate=next((x for x in list_records(root,"records/release-candidates") if x.get("release_candidate_id")==candidate_id), None)
            if candidate is None: raise LifecycleError("RELEASE_CANDIDATE_INVALID", "release candidate not found")
            review_id = _arg(args,"--review-id")
            review=next((x for x in list_records(root,"records/release-reviews") if (review_id and x.get("review_id")==review_id) or (not review_id and x.get("release_candidate_id")==candidate["release_candidate_id"])), None)
            if review is None: raise LifecycleError("RELEASE_REVIEW_INCOMPLETE", "release review not found")
            expected = _arg(args,"--expected-registry-head")
            if expected:
                current = json.loads((root/"state/registry-head.json").read_bytes()).get("head_hash")
                if expected != current: raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT", "registry head changed")
            return publish_release(root,candidate,review,package_name=_arg(args,"--package-name","ontology-package"),package_version=_arg(args,"--package-version","0.0.0"))
        if action=="attest":
            release_id=_required(args,"--release-id")
            release=next((x for x in list_records(root,"records/releases") if x.get("release_id")==release_id),None)
            if release is None: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "release not found")
            return attest_release(root,release,package_lock_id=_arg(args,"--package-lock-id"),package_archive_sha256=_arg(args,"--package-archive-sha256"))
        if action in {"inspect","verify"}:
            release_id=_required(args,"--release-id"); row=next((x for x in list_records(root,"records/releases") if x.get("release_id")==release_id),None)
            if row is None: raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", "release not found")
            return {"status":"VERIFIED","release":row} if action=="verify" else row
        if action=="list": return list_releases(root)
    if domain=="environment":
        if action in {"init","create"}: return init_environment(root,environment_name=_required(args,"--name"),environment_class=_arg(args,"--class","DEVELOPMENT"))
        if action in {"list","status"}: return list_environments(root)
        if action in {"pointer","history"}:
            environment_id=_required(args,"--environment-id")
            if action=="pointer":
                path=root/"state"/f"environment-pointer-{environment_id.rsplit(':',1)[1]}.json"
                if not path.is_file(): raise LifecycleError("ENVIRONMENT_INVALID", "environment pointer not found")
                return json.loads(path.read_bytes())
            return [event for event in read_events(root) if event.get("payload",{}).get("target_environment_id")==environment_id]
        if action=="activate":
            if subaction=="propose":
                return propose_activation(root, environment_id=_required(args,"--environment-id"), release_id=_required(args,"--release-id"), rationale=_arg(args,"--rationale",""), requested_by=_arg(args,"--requested-by","operator"))
            if subaction=="review":
                return review_activation(root, proposal_id=_required(args,"--proposal-id"), decision=_arg(args,"--decision","APPROVE_ACTIVATION"), reviewer_id=_arg(args,"--reviewer-id","operator"), reviewer_roles=_args(args,"--roles"), rationale=_arg(args,"--rationale",""), breaking_change_acknowledged="--ack-breaking" in args)
            if subaction=="execute":
                return execute_activation(root, proposal_id=_required(args,"--proposal-id"), decision_id=_required(args,"--decision-id"), expected_generation=int(_arg(args,"--expected-generation")) if _arg(args,"--expected-generation") is not None else None, expected_pointer_hash=_arg(args,"--expected-pointer-hash"), reviewer_id=_arg(args,"--reviewer-id","operator"), breaking_change_acknowledged="--ack-breaking" in args)
            return activate(root,environment_id=_required(args,"--environment-id"),release_id=_required(args,"--release-id"),reviewer_id=_arg(args,"--reviewer-id","operator"),breaking_change_acknowledged="--ack-breaking" in args,expected_generation=int(_arg(args,"--expected-generation")) if _arg(args,"--expected-generation") is not None else None,expected_pointer_hash=_arg(args,"--expected-pointer-hash"))
        if action=="rollback":
            if subaction=="propose":
                return propose_activation(root, environment_id=_required(args,"--environment-id"), release_id=_required(args,"--release-id"), rationale=_arg(args,"--rationale",""), requested_by=_arg(args,"--requested-by","operator"), activation_kind="ROLLBACK")
            if subaction=="review":
                return review_activation(root, proposal_id=_required(args,"--proposal-id"), decision=_arg(args,"--decision","APPROVE_ROLLBACK"), reviewer_id=_arg(args,"--reviewer-id","operator"), reviewer_roles=_args(args,"--roles"), rationale=_arg(args,"--rationale",""))
            if subaction=="execute":
                return execute_activation(root, proposal_id=_required(args,"--proposal-id"), decision_id=_required(args,"--decision-id"), expected_generation=int(_arg(args,"--expected-generation")) if _arg(args,"--expected-generation") is not None else None, expected_pointer_hash=_arg(args,"--expected-pointer-hash"), reviewer_id=_arg(args,"--reviewer-id","operator"))
            return rollback(root,environment_id=_required(args,"--environment-id"),reviewer_id=_arg(args,"--reviewer-id","operator"),rationale=_arg(args,"--rationale",""),expected_generation=int(_arg(args,"--expected-generation")) if _arg(args,"--expected-generation") is not None else None,expected_pointer_hash=_arg(args,"--expected-pointer-hash"))
    if domain=="activate": return activate(root,environment_id=_required(args,"--environment-id"),release_id=_required(args,"--release-id"),reviewer_id=_arg(args,"--reviewer-id","operator"),breaking_change_acknowledged="--ack-breaking" in args,expected_generation=int(_arg(args,"--expected-generation")) if _arg(args,"--expected-generation") is not None else None,expected_pointer_hash=_arg(args,"--expected-pointer-hash"))
    if domain=="rollback": return rollback(root,environment_id=_required(args,"--environment-id"),reviewer_id=_arg(args,"--reviewer-id","operator"),rationale=_arg(args,"--rationale",""),expected_generation=int(_arg(args,"--expected-generation")) if _arg(args,"--expected-generation") is not None else None,expected_pointer_hash=_arg(args,"--expected-pointer-hash"))
    raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", f"unknown lifecycle command: {' '.join(args[:2])}")

def main(argv: list[str] | None = None) -> int:
    args=list(argv or [])
    as_json="--json" in args
    debug="--debug" in args
    forbidden = sorted(_FORBIDDEN_FLAGS.intersection(args))
    if forbidden:
        command="lifecycle " + " ".join(args[:2])
        return _emit(command, {"message": "forbidden lifecycle bypass option", "options": forbidden}, code=42, status="FAIL", errors=["forbidden option: " + ", ".join(forbidden)], as_json=as_json)
    args=[x for x in args if x not in {"--json","--debug"}]
    args=_normalise_args(args)
    command="lifecycle "+" ".join(args[:2])
    try: return _emit(command,dispatch(args),as_json=as_json)
    except LifecycleError as exc: return _emit(command,{"message":str(exc),"error_code":exc.code},code=exc.exit_code,status="FAIL",errors=[str(exc)],as_json=as_json)
    except Exception as exc:  # noqa: BLE001
        if debug: traceback.print_exc()
        return _emit(command,{"message":str(exc),"error_type":type(exc).__name__},code=1,status="FAIL",errors=[str(exc)],as_json=as_json)
