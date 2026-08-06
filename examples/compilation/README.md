# Stage 06 Compilation Examples

The `expected/` folders document deterministic compilation scenarios for full,
modified, rejected, and issue-resolution confirmations. Runtime builds belong
under ignored `runtime_outputs/compilation/<compilation-id>/` and are never
imported into GraphDB during Stage 06.

Every build requires all authority inputs:

```text
CleanedPartialData + ModelingProposal + final ReviewDecisionLog
+ READY ConfirmedModelingPackage + frozen dependencies + Compiler Policy
```

The `invalid/` folders name fail-closed cases used by the security and boundary
tests. A blocked package, tampered package, unsupported mapping assertion, SHACL
violation, or ontology inconsistency must produce no formal partial output.
