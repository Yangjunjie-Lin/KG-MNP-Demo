# Human Review Workflow

The review queue orders global issues, terminology, TBox, SHACL, Mapping, ABox,
conflicts, and coverage gaps while respecting candidate dependencies. Scores
never remove an item from review. Policies define required roles, evidence,
minimum approvals, quorum, modification, blocking-issue, and self-approval
rules. `DEVELOPMENT_SINGLE_REVIEWER` is for tests and development only;
`PRODUCTION_MULTI_ROLE` requires the declared expert roles and is not silently
weakened.

Actions are `ACCEPT`, `MODIFY_AND_ACCEPT`, `REJECT`, `DEFER`,
`REQUEST_EVIDENCE`, `REUSE_EXISTING`, `MARK_DUPLICATE`, `RESOLVE_CONFLICT`, or
`COMMENT`. There is no accept-all, auto-review, model-review, bypass, or force
finalization route. A modified candidate becomes a new Core-owned revision,
gets a new semantic signature/ID, and is rechecked for namespace, evidence,
baseline, dependency, and blocking status.

Actions form an append-only hash chain. The operational hash includes
timestamps/session/display metadata; the semantic decision hash excludes it.
Deletion, edit, reorder, replay, stale proposal/prevalidation/policy, and
cross-project reuse fail verification. Finalization additionally requires all
candidates decided, all blocking conflicts resolved, accepted dependencies and
all authority/evidence closures complete, and role/quorum compliance.
