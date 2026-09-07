# Prompt 8 Final Report

## 1. Final Decision

**NO_GO_BACKEND_NOT_READY.** This is a partial 8A remediation, not completion of
Prompt 8. `WORKBENCH_BACKEND_GATE=FAIL`. Formal 8B UI acceptance and 8C browser
acceptance were not run. GraphDB licensing does not explain missing core APIs.

## 2. Baseline and branch

Source: `9ae308ef86e74a08eb4daab1e20dd66cced87b16` on
`codex/unified-services-api-sdk-p07`; target:
`codex/unified-ontology-workbench-p08`. Initial worktree was clean. Fetch matched
the fixed source. P1–P7 remote heads are ancestors. Historical tag
`kg-mnp-phase06-baseline-2026-08-30` remains
`e45da340267de8d4b7b3a54177822aa641e3a601`. Final HEAD/remote synchronization are
reported in the delivery message and the final evidence summary. No force push,
history rewrite, tag replacement, main/P1–P7 modification or PR merge is used.

## 3. 8A reproduced defects and repairs

Initial `test_prompt08_boundary.py`: 10 failed, 3 passed. Post-repair same initial
13 tests passed. Further serial tests cover real sockets, core lifecycle,
authorization, negative paths, concurrency, revocation and lease recovery.

| Gap | Actual repair | Remaining boundary |
| --- | --- | --- |
| A1 | Core initialize_workspace, ProjectManifest/ProjectLock, full layout and verified identity mapping; non-rebinding lock checks | No legacy migration; new workspace required |
| A2 | Actual configured local pack discovery, exact versions, lifecycle/capabilities/lock/availability, distinct empty/denied/parse errors | No new forestry content |
| A3 | Owner/grant-filtered projects; resolve Job then check project/Principal; separate cancel permission; hide internal handles | Evidence/download resource not implemented |
| A4 | Public and reader health contain only ALIVE; doctor requires service:admin | CLI doctor remains local detailed diagnostics |
| A5 | Scoped job and synchronous idempotency; durable unknown-outcome intent; current token revalidation; renewal and cancellation; stale completion denied | Core state commit fencing unfinished; no core-writing JOB handler enabled |
| A6 | Truthful handler catalogue; absent handlers rejected before enqueue | 39 service handlers still absent; core main workflow incomplete |

## 4–5. Actual operations and browser/API map

[Service coverage](prompt-08-service-coverage.json) lists all 53 operations,
concrete function paths, input/output declarations, permissions, resource or
compatibility route, inline/job mode, actual passing positive/negative nodeids,
status and blockers. No handler is mechanically labelled `explicit`.
[Requirement map](prompt-08-requirement-test-map.json) separately records browser
tests as NOT_RUN. Current measured breakdown: 12 implemented/tested, 2 implemented
but missing positive service verification, 39 declared only. Empty failure and
permission-rejection tests are not positive business execution evidence.

## 6–8. Security, workspaces and jobs

The existing TokenStore remains the only credential authority. Expiration,
revocation and current grants are re-read. Client `__principal` and reviewer/
approval fields are rejected recursively. Service accounts cannot approve scope
or review. Empty project scope is not global. Job result/event network shapes
do not forward arbitrary legacy paths. Health and ProjectHandle.root no longer
leak service filesystem locations. Wrong Origin, DTO input echo and malformed
requests have regression coverage.

Browser cookie sessions, logout/cache clearing, CSRF session protection and
evidence-preview/download permissions remain **not implemented**. No browser
security certification is asserted. The API remains Bearer authenticated.

Core workspace ID `project-<digest>` and service `urn:kg-mnp:project:<digest>` are
explicitly verified against manifest, exact Pack/version and registry identity.
Old unowned/unmapped records remain `LEGACY_INCOMPLETE/NEW_WORKSPACE_REQUIRED`;
files are not overwritten. Lock checks preserve existing bytes and refuse
stale/tampered locks. Job idempotency is principal+project+operation+key; the
legacy table is retained. Queued cancel is CANCELLED; running cancel is only
CANCEL_REQUESTED. Expired leases become RECOVERY_REQUIRED and are not replayed
blindly. Core state fencing remains a blocker, not a claimed fix.

## 9–13. UI and semantic workflows

The Chinese domain-neutral [information architecture](../architecture/workbench-information-architecture.md)
is a plan only. Unified navigation, frontend stack/design system, responsive
layout, keyboard QA, graph/table/evidence linking, mapping forms, scope/CQ,
review comparison, compilation reports and version/environment dialogs are
**not implemented or browser-verified**. No screenshot is claimed.

Core package/release/pointer semantics are preserved: VALIDATED_UNPUBLISHED,
IMPORTED_VERIFIED, RELEASED and CONTROL_PLANE_SELECTED are not one state.
Observed deployment is separate. There is no new UI or API full-chain release
success, no false CQ oracle and no release skip/force mechanism.

## 14–16. Cross-domain results and protected assets

See [graded matrix](prompt-08-cross-domain-report.md). Minimal/MNP/Forestry P8
independent browser workflows are NOT_RUN. Forestry remains PLANNED 0.1.0;
the authorized synthetic EXPERIMENTAL 0.2.0 pack and new digest are **not built**.
No old project resolves its requested version to a newer one implicitly.
`generate_mnp_prompt01_content_golden.py --check` reports 84 assets current.
Minimal, MNP, forestry manifests/locks and public 115 schemas are unchanged.

## 17–18. Real HTTP IDs and negative cases

Real socket+HTTP SDK+durable worker gate created:

`urn:kg-mnp:project:caa24c035b6e219778e94bc651dac29e110c470212ce5fe37030dca3058e2ddb`.

Identity, minimal discovery, valid Workspace, workspace validation and empty
registry verification passed. Source upload resource returned **404** and
Source handler returned **501 OPERATION_BLOCKED**. There is no resulting
Ingestion Job, KG-IR, Confirmed Package, compiled Package or Release ID from this
HTTP chain. Owned server and worker were stopped. Gate JSON lives in ignored
`runtime/prompt08-http-gate-1070f0a5/backend-gate.json`.

Tests include outsider empty-scope project/job rejection, forged identity,
service-account human-approval rejection, revoked/expired credentials, exact
version failure, malformed pack parsing, stale/tampered lock rejection,
different-body key conflicts, concurrent/restarted idempotency, interrupted
outcome recovery, cancellation and lease expiry. Browser multi-tab CAS,
evidence XSS/raw HTML, oversized uploads, duplicate release and full failure
recovery through a unified UI are NOT_RUN.

## 19. Integrations

GraphDB live retains the P7 external-license blocker and was not executed.
The service integration handlers are separately missing, not merely license
blocked. Local OMS/ODS and WebVOWL core implementations exist but are not
connected/verified through a complete released Workbench workflow. Workflow
outbox unit coverage means REQUEST_ENQUEUED, not external business completion.
Live LLM/OCR/ASR/Vision success is not simulated.

## 20–21. Files, old UI, packaging and startup

Changes are limited to services/API/jobs/config, byte-keyed schema-verdict
caching (no schema bytes changed), service/contract tests, gate/evidence scripts,
Make targets, authorized snapshot and honest documentation. No files are moved
or deleted. All nine old UI files remain with explicit per-file reasons in
[migration inventory](../workbench/legacy-migration.md); retirement is incomplete.

[PowerShell/POSIX startup and recovery](../workbench/backend-remediation.md)
documents same-config web/worker, explicit preparation, health and owned-process
shutdown. Wheel and sdist build the partial Python 0.7.0 package, not a Workbench
bundle. No frontend npm build, lockfile, clean-installed Workbench, deep-link SPA
or production deployment is claimed. Clean Python wheel installation is recorded
separately and does not prove a frontend package exists.

## 22–23. Test evidence and visual acceptance

Initial final collection: **1506 nodeids**; four atomic-commit tests were added
after reproducing the Windows write failure. The refreshed collection and union
are recorded in the verification summary. Serialized service/integration/P7
core regression and cache safety set: **63 passed, 0 failures, 0 skips**.
Logs/JUnit/dependency versions and SHA-256 live under ignored
`runtime_logs/prompt08/`; final summary records command outcomes independently.
Repeated 13/32/49/63 test runs are not added as unique coverage.

The initial long-running aggregate/full runs were interrupted when the
byte-keyed schema-check optimization was applied and then restarted. They are
INCOMPLETE, not PASS. A diagnostic run with faulthandler crashed; that run is not
passing evidence. A first HTTP gate hit its short timeout, then a bounded 180s
client rerun reached the real missing-handler failure. Such diagnostics are
not mislabeled as external-license failures.

No Workbench screenshots, visual baselines, browser traces/videos, accessibility
scan, manual keyboard examination, 1000-row performance measurement or graph
benchmark were produced. Required visual acceptance is NOT_RUN, not passed.

## 24–25. Compatibility, snapshot and risks

Catalog remains 1.3.0 with 115 contracts. API stays v1; compiler and pack policy
versions are unchanged. Existing ProjectLock and portable package bytes are not
rewritten. P7 frozen tree was verified from git archive: 1486 files,
`d382179e7322ccb802a5b01d4bbf7fa3f7c113a597c74e932fb52297b19f72b3`.
Authorized P8 protected tree includes new `workbench` root (currently absent),
with no protected root removed; new semantic tree is 1498 files,
`595558b7b32f0b64cd84729349dc81aae58dde6bc93624188646766727ce69cd`.

The content cache stores only a metaschema verdict keyed by exact raw bytes.
Every call still reads files, checks IDs and verifies required digests; mutated
schema bytes do not inherit a cached valid verdict. Negative tests cover this.
Old compilation artifact writes also receive a bounded retry for transient
Windows access/sharing-denied rename failures. Repeated/permanent denial still
fails; a concurrently-created destination is not replaced by the retry helper.
Risks remain: missing core service writes/fencing, browser sessions, resource
families/typed responses/pagination, all UI acceptance, forestry content,
release-ready Workbench packaging and any incomplete final aggregate result.
Deprecation warnings (multipart, websockets, rdflib) are retained in receipts.

## 26–28. Commits, P9 and final Git state

Logical commits separate service/security corrections, schema-check performance,
gate/evidence/freeze work and the final report. Full commit IDs and final remote
HEAD are supplied with delivery rather than embedding a self-referential HEAD
inside its own commit.

P9 admission is **blocked by unfinished Prompt 8**, not by a new roadmap. The
[P9 checklist](../workbench/p9-handoff.md) lists retained old entrypoints and
Stage/Phase code, duplicate validators, test/CI consolidation, dependencies,
release packaging, security scanning and final full-chain acceptance. No P9
repository-wide cleanup is claimed. Final Git status and remote consistency
must be checked after the normal target-branch push.
