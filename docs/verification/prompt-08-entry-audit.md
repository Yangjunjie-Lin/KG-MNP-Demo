# Prompt 8 entry audit

Source: `9ae308ef86e74a08eb4daab1e20dd66cced87b16`.
Branch: `codex/unified-ontology-workbench-p08` (created from the exact source).
Initial worktree: clean. Fetch completed; origin source matched. Historical tag
`kg-mnp-phase06-baseline-2026-08-30` resolved to
`e45da340267de8d4b7b3a54177822aa641e3a601`.
All seven remote Prompt branch heads were verified as ancestors of source.

## Observed implementation, not catalogue claims

- `services/projects.py:create_project` initializes only a lifecycle registry;
  it does not call `workspace/service.py:initialize_workspace`.
- `facade.py:project.lock` writes a non-contract `status=LOCKED` document.
- `domain-pack.discover` is project-scoped and returns a constant empty list.
- `authorization_policy.py` treats empty `project_ids` as unrestricted.
  `project.list`, `project.open`, `job.get`, and `job.events` miss object checks.
- Public `/healthz` exposes `workspace_root`; authenticated health exposes the
  same administrator diagnostics. Project DTOs include filesystem roots.
- Job idempotency uses only project/key; synchronous writes have no ledger.
- Worker trusts serialized Principal grants, lacks renewal/cancellation, and
  fences completion only. CLI worker exits after one claim.
- Facade ends with 501 for most declared operations. Core lifecycle E2E tests
  are not HTTP/SDK/browser main-workflow tests. P7 queue tests deliberately
  assert FAILED, not business completion.
- P7 coverage uses `service_handler="explicit"` for all 53 entries; this is
  declaration coverage, not verified functionality.
- The P7 summary explicitly records incomplete aggregate offline gates.
  GraphDB live is separately blocked by missing external license.

## Frontend entry review

`web/workbench/assets/app.js` is a read-only publication-attested explorer using
`/workbench/api/view/*`, with stage/phase language and MNP defaults.
`web/diagnostics/assets/app.js` reads publication diagnostics via a distinct API.
`web/governance/assets/app.js` submits amendment/review requests to a third API,
including user-supplied reviewer labels. These are not a unified authenticated
ontology modeling workflow. No migration/deletion is authorized by a successful
replacement until the backend gate passes. Retain their semantic/security tests.

## Gate discipline

New boundary regressions are run RED before fixes. Results and command log
digests are recorded separately; a 202 is never a successful business operation.
8B formal browser acceptance and 8C acceptance are gated on a real complete 8A
HTTP SDK flow. NOT_RUN is not PASS. No production-readiness claim is made.
