# Prompt 8 backend remediation: operations and recovery

This branch is a **NO_GO backend remediation**, not a complete workbench release.
Package version remains 0.7.0: no semantic compiler policy, public Contract,
minimal/mnp lock, or forestry pack version is changed merely for service work.

## Run the service and worker

Install the existing Python package dependencies explicitly: `python -m pip
install -e ".[dev]"`. All runtime directories below are ignored. Source checkout
development discovers the checked-in domain packs; installed deployments must
configure their exact administrator-controlled root.

PowerShell (two terminals, same configuration):

```powershell
$env:KG_MNP_DOMAIN_PACKS_ROOT = (Resolve-Path domain_packs).Path
python -m kg_mnp service serve --workspace runtime/p08-service
```

```powershell
$env:KG_MNP_DOMAIN_PACKS_ROOT = (Resolve-Path domain_packs).Path
python -m kg_mnp service worker --workspace runtime/p08-service --worker-id local-worker
```

POSIX:

```sh
export KG_MNP_DOMAIN_PACKS_ROOT="$PWD/domain_packs"
python -m kg_mnp service serve --workspace runtime/p08-service
# A second terminal with the same root/environment:
python -m kg_mnp service worker --workspace runtime/p08-service --worker-id local-worker
```

`worker --once` is the explicit one-claim mode. Ctrl+C stops only the foreground
process launched in that terminal. Do not kill an unknown process on a port
conflict. The real HTTP gate owns its server and worker and stops both. Public
`/health/live` and `/healthz` return only `{"status":"ALIVE"}`. CLI `doctor`
includes local paths; HTTP doctor requires `service:admin`.

Create credentials only with the existing administrator CLI token command.
Do not put the printed token in source, a URL, screenshot or browser storage.
There is no public registration or browser login/session endpoint on this
partial branch. No cookie-authentication/CSRF assurance is claimed.

## Project identity and old records

Creation requires `name`, `domain_pack`, `domain_pack_version`; path input is
not accepted. The handle ID maps to `project-<digest>` in core ProjectManifest.
Registry identity binds the handle ID; the registry lives at the workspace's
`registry/lifecycle` directory. Server-side metadata records the owner and exact
pack selection. Network project representations never include `root`.

Empty project scope is not global: it grants no foreign projects. Owners can
open newly-created projects; explicit nonempty scopes narrow a credential.
Global management requires explicit `project:admin` (or administrator `*`
permission), not `project_ids={"*"}`. Per-operation permission remains required.

`project.lock` checks the existing core lock using `generate_project_lock(check=True)`.
It refuses invalid or stale workspaces; it never rebinds artifacts. P7 records
without a verifiable mapping/owner remain `LEGACY_INCOMPLETE` and
`NEW_WORKSPACE_REQUIRED`. No migration button/implicit hash repair is provided.
Malformed catalog files fail closed. Administrator recovery must preserve old
files and establish authority independently; this implementation requires a
new workspace instead of guessing ownership.

## Idempotency and jobs

Use Idempotency-Key for writes. The synchronous ledger scopes principal,
project, operation and key; changed bodies conflict. A durable intent is saved
before mutation. Interrupted/ambiguous requests remain `RECOVERY_REQUIRED`, not
automatically replayed. Job keys have the same scope in a separate v2 table;
old ambiguous keys require administrator reconciliation. No old table is erased.

Worker identity comes from the current token store, not queued grants. Missing,
revoked and expired credentials fail. Job reads/events/cancel first resolve the
Job's project and submitting Principal; cancellation separately requires
`job:cancel`. Queued cancellation is terminal; running cancellation is only a
request. Lease expiry prevents renewal/completion and is conservatively marked
`RECOVERY_REQUIRED`; no unknown external effect is retried automatically.

**Core state-commit fencing is unfinished.** For that reason no core-writing
JOB handler is enabled. Missing handlers return 501 *before enqueue*, and old
queued operations fail closed after current identity checks. This is a safety
boundary, not fulfillment of ingestion/modeling/compile/release requirements.
Legacy arbitrary job result/error details are not forwarded as network payloads.

## Verification

`python scripts/run_prompt08_verification.py NAME -- COMMAND ...` saves a unique
ignored directory with command, exit code, duration, dependency versions, log
SHA-256 and (for pytest) JUnit, collection and per-node results. Do not add
counts from repeated runs. `make verify-workbench-backend` exercises a real
socket, HTTP SDK, valid workspace and real worker, then reports the missing
upload/Source service workflow and exits nonzero. It must not be converted to
PASS by accepting 202, mocking handlers or bypassing the HTTP boundary.

There is no new production frontend bundle, wheel-bundled Workbench, browser
installation, screenshot set, accessibility certification or deployment claim.
