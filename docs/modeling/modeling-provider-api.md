# Modeling Provider API 1.1

Plugin API 1.1 adds the `modeling-provider` kind without changing Plugin API
1.0 or its 13 ingestion plugins. A manifest declares input/output contracts,
capabilities, determinism, side effects, `network_policy=DENY`, and
`authority_level=PROPOSAL_ONLY`. Installed external distributions are
discovered from metadata without importing their implementation and remain
disabled until explicitly allowlisted.

Providers receive an immutable request containing bounded, already-validated
context. They receive no workspace service or artifact writer and return only
candidate drafts. Drafts cannot contain final IDs, semantic signatures,
review/confirmation decisions, locks, executable code, arbitrary RDF, local
paths, secrets, or publication operations. Core validates the response,
normalizes Unicode and IRIs, checks closure and limits, computes semantic
signatures and candidate IDs, merges provenance, and detects conflicts.

Built-ins are manual import, baseline reuse, deterministic rule mapping, and
recorded model output. They perform no network access. Python plugins are
trusted installed code governed by policy and conformance tests, not an OS
sandbox.
