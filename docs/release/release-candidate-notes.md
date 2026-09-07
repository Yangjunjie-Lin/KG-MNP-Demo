# Delivery scope — NO_GO_OPEN_CORE_REQUIREMENTS

This branch is a recoverable development increment, **not complete final
consolidation and not a verified release candidate**. No candidate tag or public
Release is authorized by these results. Product version: 0.9.0.dev0; compiler,
contract and Domain Pack versions remain independent.

## Baseline and actual increments

Source: 9da17d126cb37166ff06084080770108da20afbe.
Target: codex/toolchain-final-consolidation-p09.
The fixed P8 1498-file protected tree was actually checked at entry and again
from git archive. P1-P8 ancestry and the historical baseline tag were checked.
The annotated pre-consolidation tag points to the exact P8 source, not a release.

G0: baseline audit and a single requirement ledger established. Existing source
and reports were read; the full old-code caller/retirement audit is incomplete.

G1: real TCP upload/Source/Batch/Worker/ingestion/KG-IR/Evidence/raw download chain.
Core publication now uses the existing project authority mapping and a
credential/lease/fencing/CAS-protected atomic commit receipt. Actual fault tests
cover precommit lease loss, superseded fencing, revocation, cancellation,
computation failure, before/after publication exceptions, restart reconciliation
and lost Job completion. Tests simulate process-death boundaries; hard-kill at
every filesystem-write boundary and power-loss behavior are not certified.

G2: nonempty Minimal scope/approval/CQ/baseline/terminology/alignment/proposal,
per-candidate human review, confirmation and real fixed Reasoner/SHACL/CQ/
Provenance compilation. The public modeling subset does not yet expose all core
manual/recorded Provider, edit/revalidation and conflict-resolution capabilities.
The Workspace's old blanket rejection of all confirmed files was replaced by
actual confirmation manifest/authority validation; arbitrary files still fail.

G3: actual package import with source ProjectLock bytes/digest, initial release
candidate/review/CAS publish/attestation and nonempty fixed-package object query.
The complete successor change/regression/environment/rollback services remain
open. Local package query is not proof of a complete version-bound ODS product.

G4: one Chinese React/TypeScript/Vite workbench, session login, projects, sources,
evidence table, scope/CQ forms, mappings, individual review, compiler reports,
initial release, object query and jobs. A real Minimal browser scenario passed
during development with no mocked core API. Screenshots were actually opened.
Full Forestry/MNP/fourth-pack workflows, candidate editing, complete evidence and
version linking, 1000-row/200-node benchmarks and accessibility audit are absent.

G5: runtime source-tree freeze converted to fixed-history audit; service DTO
tests adapted while preserving security assertions; receipt plugin renamed to a
capability name; README and commit-boundary guide updated. Old UI and business
entry retirement/complete CI migration are **not done**, since their replacement
equivalence gate has not passed. No archive/legacy tree was created. Existing
P8 receipt path prefixes were normalized for hygiene, without changing outcomes.

G6: final fixed-revision test/build/install evidence is recorded separately in
final-verification.json once actually run. Development PASS results at different
revisions must not be combined into a final full-suite claim.

## Remaining service operations and other required work

The original 53 rows are retained. 41 currently have application adapters; this
does not mean 41 complete product requirements. Remaining declared operations:

- change.diff, change.impact, change.regression, change.evaluate;
- environment.activate, environment.rollback;
- visualization.export;
- integration.plan, integration.review, integration.execute, integration.verify;
- workflow.enqueue.

Forestry remains the unchanged 0.1.0 PLANNED pack; the authorized synthetic 0.2.0
upgrade has **not** been delivered. Minimal/MNP assets and all 115 public schema
files are unchanged relative to P8. MNP's 84-asset preservation check was run.
No new Forestry lock/digest or pilot effect is claimed. Existing packages retain
their versioned schemas; the compiler's implementation files were not edited.

Additional missing scope is explicitly retained in final-requirements.json:
production multi-role full-browser negatives, unsafe preview/query adversarial
coverage, complete CAS/recovery fault matrix, historical-package clean-install
coverage, Linux execution, full UI/CLI/API/SDK parity, old implementation cleanup,
test migration and CI execution, full release build/install verification.

## Dependencies and evidence boundaries

The Python environment was created with venv and installed from declared extras;
requirements-dev.lock records its dependency resolution. Existing backend pins
were retained; this is not an exhaustive dependency-vulnerability audit. Node 24
matches the selected Vite engines. Frontend dependencies are exact and locked;
npm install reported zero advisories at that time. Legacy Python Playwright is
separate from the new Node browser runner. Browser/JAR acquisition is preparation,
not core runtime. No host pytest/httpx fallback is needed.

The development-version installation reproduced and fixed a bundled-plugin
version parser defect. PEP 440 development/RC versions are compared correctly;
snapshot spelling is explicitly normalized to SemVer without changing frozen
schemas. Stable versions are unchanged and external plugin matching is still
exact. The independent plugin-wheel test also exposed undeclared setuptools and
wheel tooling; both are now explicit pinned build/development requirements.
These original failures are preserved in the ignored logs, not called external
blockers. MNP's actual unchanged Pack version is 1.0.0 (not 0.1.0).

Raw JUnit/logs/screenshots and synthetic IDs live under ignored runtime_logs/p09.
Browser traces/video are disabled to avoid recording login credentials. Source
and job data, sessions, tokens, node_modules and dist are not committed. Wheel
and sdist include generated static resources from the same build pipeline.

GraphDB live remains an optional external-license/environment blocker. Missing
local adapters and local core requirements are **not** attributed to that blocker.
Outbox/Pointer changes are not business execution or external deployment.

## Research claims

Implemented mechanisms include contract-bound engineering, evidence-bound KG-IR,
separation of proposals/review/compiler authority and integrity-bound lifecycle
records. These mechanisms are evidenced by the concrete services/core tests, not
schema/file counts. Academic novelty, source truth, business correctness,
cross-industry generality, forestry field effectiveness and production security
certification have not been demonstrated. Hashes prove byte bindings, not truth;
OWL/SHACL/CQ results are limited to the actual inputs, constraints and Oracles run.

## Fixed-revision verification actually completed

Tested commit: `3c0d0ad18e9640ceacc60502e227354cfff939d0`.
Source-tree digest: `1cee0c28d4ef2012ab8056259661ba5e30809fc6038c85cdb4f876065f6de88e`.
The earlier fixed attempts are superseded and were not merged into this result.

- Complete Windows collection: 1575 unique nodes. Serial 449 + parallel 1126,
  disjoint union exactly equals collection. Result: **1566 passed, 9 skipped,
  0 failed/errors**. Skips and original command outcomes are in final-verification.json.
- Ubuntu 24.04 / Python 3.12.3: **60 POSIX tests passed, no skips** on an actual
  source checkout of the tested commit, with a clean installed dependency environment.
  The first Linux failure exposed drive-path rejection and three frozen CRLF schema
  byte bindings. The path code and exact checkout rules were fixed; schema blobs,
  IDs and old hashes were not changed. This is not a full Linux semantic suite.
- Real Chromium 153 Minimal browser scenario passed in about 442 seconds with
  Source, KG-IR, Proposal, per-item synthetic-human Review, fixed Reasoner,
  Package, initial Release and nonempty object query. No core API was mocked.
- Frontend type/build, npm audit, backend Ruff, hygiene, pip consistency,
  MNP 84-asset preservation, OpenAPI export and requirement-generator module check passed.
- Wheel/Sdist built; sdist actually rebuilt into a wheel. An isolated Windows wheel
  probe read packaged Contract/Policy resources, loaded Workbench/deep links and
  confirmed API 401/404 boundaries without importing source-tree code.
- Six final screenshots were actually inspected. Dense review tables and incomplete
  UX/a11y/benchmark coverage remain limitations, not a completed visual acceptance.

Main browser IDs:

    Source: urn:kg-mnp:source:a6b96e697f242db622efb316e435372f68ce9881611213756e7736b9b406cbb6
    KG-IR: urn:kg-mnp:kg-ir-dataset:85a7bec0652e59ac231cadf29fe6d9c510539fb73643132277e7bad780ed861e
    Proposal: urn:kg-mnp:ontology-modeling-proposal:aecdd0bcd56c598d89c5f626f2229b8fe62d65e59dc309484a5308c30ee9dec8
    Review: urn:kg-mnp:ontology-review-queue:80ea2665657764f1cc18df6f0acaac81321df174f9440f6bc37aa12c6cd63202
    Package: urn:kg-mnp:ontology-package:f18aa1412acaaecfff05eb4b21cc080c776192b70a94c93091080bb60155b16c
    Release: urn:kg-mnp:release:86374b5d36f9f92fa67d99eecf6418d13268c62358764a983499395c7af4d649

The exact Job/Scope/Confirmation/Compilation/Attestation IDs and artifact hashes
are in final-verification.json. Development artifacts (not release candidates):

- `runtime/p09-final-distribution/domain-packs-and-minimal-example-3c0d0ad.tar.gz` — SHA-256 `b1a6423dfee6d6e23f989eb395dd04e818be0757db12d726c173ab92c7cbac3a`
- `runtime/p09-final-distribution/kg_mnp_toolchain-0.9.0.dev0-py3-none-any.whl` — SHA-256 `0121ce397964c19e130bfcd7d81f86643667ef152cf6badd2d57c5dbed1957c3`
- `runtime/p09-final-distribution/kg_mnp_toolchain-0.9.0.dev0.tar.gz` — SHA-256 `d1f1871b549be8d3b7da26e8605cf974458762140f6bc9b48e4f8ea7adee864d`

The delivery commit is an evidence-only successor of the tested commit. Its exact
SHA is supplied after creation; no file contains its own commit hash. Only
final-verification.json, final-requirements.json and these notes are excluded from
the tested-input comparison. These files are not included in Wheel/Sdist inputs.
All source/config/test/build inputs must match the tested revision.

The original required operation map remains complete, with 12 declarations still
unconnected and several implemented operations explicitly partial. No candidate
tag, public Release, main merge, force push or production deployment is performed.
The original 1687 tracked files became 1726 at the tested commit; this is inventory,
not a quality score. Only the shared receipt helper moved; full retirement and CI
reorganization are not complete.

Raw acceptance archive: `runtime/p09-final-distribution/acceptance-evidence-3c0d0ad.zip`
(958548 bytes), SHA-256
`bb24845ce801d08c388b1a71c1be3191e5176d7229e8012729a5c5bc26ddb93b`.
Its 93 selected files passed the credential-pattern scan; runtime workspaces,
source blobs, session/token stores and browser auth state are not included.
