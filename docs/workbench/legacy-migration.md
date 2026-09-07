# Old frontend inventory and migration status

No old file is deleted without a verified equivalent. Backend gate failure
prevents declaring retirement complete; all nine existing files are retained.

| Files (each retained) | Existing behavior | Intended replacement | Acceptance / reason retained |
| --- | --- | --- | --- |
| `web/workbench/index.html`, `assets/app.js`, `assets/styles.css` | Publication-bound read-only ontology/entity/fact/provenance/review explorer | Browse/objects + evidence + review history | NOT_RUN; new views/API incomplete |
| `web/diagnostics/index.html`, `assets/app.js`, `assets/styles.css` | Derived diagnostic summary, issues, trace | Quality/evidence + compilation diagnostics | NOT_RUN; new diagnostics views incomplete |
| `web/governance/index.html`, `assets/app.js`, `assets/styles.css` | Legacy future-amendment proposal/review with revision/head preconditions | Controlled modeling/review + lifecycle change views | NOT_RUN; human-authenticated replacement incomplete |

These assets are not served as a new unified Workbench by the service API. No
iframe wrapper, duplicate archive, safe redirect or retired URL is claimed.
Their existing path-security, authority and semantic-integrity tests remain.
P7 service test updates require an explicit pack when creating a workspace and
assert missing handlers fail before enqueue; durable job failure, idempotency,
fencing and project isolation assertions were retained, not deleted.
