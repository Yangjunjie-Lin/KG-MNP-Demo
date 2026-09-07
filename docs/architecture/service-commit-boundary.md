# Service commit and recovery boundary

The existing project catalogue is the service-to-core Workspace authority. Core
operations execute in a private **full copy** of its current Workspace. The
public mapping changes only after core execution and validation. This is local
copy-on-write, not a distributed registry.

Commit lock order: existing TokenStore metadata lock, JobStore SQLite writer
transaction, existing project metadata lock. Inside this sequence the service
rechecks credential identity/permissions, project ownership, live lease/fencing,
expected revision and input tree digest. One atomic catalogue replacement
contains the new Workspace mapping AND credential-bound commit receipt.
Computation happens outside the locks so revocation/cancellation can win.

ExecutionContext binds project, operation, job/attempt, principal/grant reference,
request/input digests, fencing token and expected revision. Idempotency remains
principal + project + operation + key. Different content with the same key is a
conflict. Client-serialized Principal/grants are never execution authority.

Before-publication failure leaves the mapped Workspace unchanged. Normal cleanup
removes private temporary output. Abrupt death may leave an unselected generation,
which is non-authoritative and is not automatically deleted. After-publication
response loss is reconciled from the atomic receipt and generation bytes; the
operation is not rerun. Unknown expired jobs stay RECOVERY_REQUIRED. External
side effects have no exactly-once claim. Process-crash tests do not certify
power-loss durability across arbitrary filesystems.

Service-managed workspaces must only be mutated through the service, not direct
legacy CLI writers. Runtime generations are retained for recovery. No automatic
garbage collector, storage quota, distributed transaction or large-workspace
performance guarantee exists. The catalogue read size is bounded; this is a
small local-example implementation, not high-volume multi-user infrastructure.

Browser sessions reference the one TokenStore. Opaque random secrets are stored
as digests, cookies are HttpOnly/SameSite=Strict/Secure, except for explicit
loopback HTTP development. Unsafe ambient-cookie requests require same Origin
and CSRF proof. Logout/identity change clears browser caches. Closing a tab,
logout or session expiry does not revoke the parent credential or cancel accepted
jobs. Credential expiry/revoke or loss of project permission blocks later commit.
Cancel Requested is not Cancelled; committed operations cannot be undone by
cancelling their Job.

Human roles come from server grants; service accounts cannot approve. Release
publication matches actions to credential-bound service commits and replays
quorum. The explicitly configured single-reviewer development profile does not
prove production multi-role acceptance. Full candidate modification/conflict and
lifecycle services remain open requirements.

Tests: tests/services/test_core_fencing.py, test_browser_sessions.py,
test_source_workflow.py and test_modeling_workflow.py.

The baseline-reuse provenance correction changes the compiler implementation
digest: mapping alignment candidates no longer shadow reviewed TBox reuse
authority. The frozen 0.5.0 snapshot contract is retained, but its implementation
digest is different; existing plans fail the snapshot comparison and require a
new plan. No old snapshot is claimed identical and old package bytes are not
rewritten. The provenance closure gate and orphan detection remain mandatory.
