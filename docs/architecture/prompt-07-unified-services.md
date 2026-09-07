# Prompt 7: unified services and integrations

The 0.7 application boundary is `kg_mnp.services.ApplicationService`. The
local CLI, `LocalClient`, `HTTPClient`, and FastAPI routes all construct an
explicit `OperationRequest` and call the same operation catalogue. No API
route shells out to the CLI and no SDK parses CLI output.

The service authenticates bearer credentials from the local `TokenStore`,
checks permissions and project scope, records an audit event, and either
executes an inline read/write or creates a durable job. Client-supplied
reviewer, role, approval, quorum, and system-actor fields are rejected.
Human approval is derived from the authenticated principal and operation
policy; service accounts cannot satisfy human approval operations.

## Request flow

```mermaid
flowchart LR
  C[CLI / Local SDK / HTTP SDK] --> S[Application Service]
  S --> A[Principal + Project Authorization]
  A --> I[Idempotency + Audit + Artifact Resolver]
  I --> K[Workspace / Ingestion / Modeling / Review / Compiler / Lifecycle]
  K --> X[Integration Service]
  X --> O[OMS / ODS / File Export / WebVOWL / GraphDB / Workflow]
```

## Durable job flow

```mermaid
sequenceDiagram
  participant H as HTTP/SDK caller
  participant S as Service
  participant J as SQLite Job Store
  participant W as Worker
  participant K as Core commit
  participant X as External target
  H->>S: authenticated OperationRequest + idempotency key
  S->>J: QUEUED (request digest)
  J-->>H: ACCEPTED(job_id)
  W->>J: lease + fencing token
  W->>K: execute and revalidate preconditions
  alt crash before commit
    W--xJ: lease expires
    J->>W: recover with new fencing token
  else core commit succeeds
    K->>J: SUCCEEDED(result)
  end
  alt external result unknown
    X--xW: timeout / ambiguous commit
    W->>J: RECONCILIATION_REQUIRED
  else approval missing
    W->>J: BLOCKED(HUMAN_APPROVAL_REQUIRED)
  end
```

The environment pointer remains a control-plane selection. It is not an
external deployment receipt. GraphDB deployment has its own
`DeploymentBinding`/`IntegrationReceipt`, and workflow outbox enqueue is not
business execution success.

## Boundaries handed to P8

P8 can consume the operation catalogue, project handles, job records, review
records, package/release metadata, desired-versus-observed deployment fields,
and explicit OMS/ODS pagination. P7 does not build a Workbench UI.
