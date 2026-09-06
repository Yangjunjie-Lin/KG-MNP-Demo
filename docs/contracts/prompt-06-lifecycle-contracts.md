# Lifecycle Contract Catalog 1.3

Catalog 1.3 retains the 83 Prompt 5 schemas byte-for-byte and adds 31
lifecycle schemas (including the shared lifecycle definitions). The semantic
compiler and package schemas remain on their Prompt 5 policy/schema versions;
the public package identity is 0.6.0. Generation is deterministic through
`scripts/generate_prompt06_contracts.py` followed by the existing catalog lock
regenerator.

Lifecycle contracts reject unsafe paths, links, executable intent, non-UTC
timestamps, cross-registry references, and uncontrolled identifiers.
