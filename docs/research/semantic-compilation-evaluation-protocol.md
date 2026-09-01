# Semantic Compilation Evaluation Protocol

Each evaluated run records the exact Confirmed Package, policy/snapshot, plan,
Domain Pack Locks, engine versions, machine-independent semantic IDs, formal
reports, package lock and archive hash. Report: input-attestation pass rate;
confirmed-candidate compilation coverage; TBox/ABox/SHACL statement counts;
mapping coverage; RDF round-trip equivalence; OWL profile/consistency pass
rates; SHACL conformance; required-CQ pass rate; provenance and evidence
lineage closure; package integrity; build/archive reproduction; compilation
and reasoner time; peak memory; and package size.

Runs with unavailable external prerequisites are reported as unavailable, not
passed. Compare two clean workspaces at different absolute paths using the same
logical inputs and explicit versions. Operational receipts/times are excluded
from authoritative equality.

Compilation coverage is not semantic accuracy. OWL consistency is not business
correctness. SHACL conformance checks only declared constraints. CQ pass applies
only to its query and oracle. Provenance closure does not establish evidence
truth. Prompt 5 neither evaluates LLM accuracy nor proves cross-industry
performance or business improvement.
