# Deterministic Identifiers

Stage 04 uses `KG-MNP Canonical JSON v1`: UTF-8, sorted object keys, fixed
compact separators, direct Unicode, and rejection of NaN and Infinity. This
profile is deliberately not claimed to implement RFC 8785.

SHA-256 over semantic content produces stable URNs:

```text
urn:kg-mnp:input:<sha256>
urn:kg-mnp:modeling-proposal:<sha256>
urn:kg-mnp:candidate:<sha256>
urn:kg-mnp:issue:<sha256>
urn:kg-mnp:dependency:<sha256>
```

An object's own ID is excluded from its content projection; a Proposal's ID
and `proposal_semantic_hash` are both excluded from the Proposal projection.
No timestamp, process ID, random UUID, absolute path, duration, or log location
enters semantic content. Candidate, issue, and unmapped-field arrays are
sorted before the Proposal hash is computed.

