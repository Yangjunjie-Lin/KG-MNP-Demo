# Operation coverage matrix

The machine-readable source is `kg_mnp.services.operations.coverage_matrix()`.
Each catalogue entry has an explicit operation ID, contracts, permission,
project scope, execution mode, side-effect class, idempotency policy,
preconditions, and audit policy. Unsupported product operations remain in the
catalogue and fail with `OPERATION_BLOCKED`; they are not silently omitted.

The service currently provides executable handlers for project creation/list/
open/validation/lock, registry verification, package/release/environment
inspection, operation catalog inspection, and job inspection. The remaining
product operations are explicit service contracts awaiting their corresponding
core implementation; they are exposed as blocked rather than bypassing P6
validation.
