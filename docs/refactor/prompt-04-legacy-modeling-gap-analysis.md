# Prompt 4 Legacy Modeling Gap Analysis

## Why the legacy contracts cannot be reused directly

`ModelingProposal 1.0` is based on cleaned-partial-data, permits no schema delta candidates, and was designed primarily for ABox-style candidate confirmation. Its evidence references predate the Prompt 3 EvidenceRecord/KG-IR closure. Extending it in place would silently broaden a stable public contract and expose the old compiler to structures it does not validate.

`ReviewAction 1.0` and `ReviewDecisionLog 1.0` address the old candidate model. They do not provide a dependency-ordered terminology/TBox/SHACL/Mapping/ABox queue, conflict resolution objects, modified-candidate re-prevalidation, separate operational and semantic hashes, or cross-project replay protection for the new control plane.

`ConfirmedModelingPackage 1.0` contains objects that are too broad for a closed Prompt 5 handoff, and its publication manifest relationship is not a safe authority boundary for the new candidate partitions. The legacy compiler cannot safely consume Prompt 4 TBox, Mapping, or SHACL candidates without a new deterministic adapter.

## Compatibility approach

- Preserve every legacy schema byte and public `kg_mnp.modeling` API.
- Preserve the legacy CLI fallback and Stage 06 compiler behavior.
- Add a distinct Prompt 4 schema family with unique identifiers.
- Add a `modeling/control_plane` wrapper that consumes validated Prompt 3 KG-IR/Evidence artifacts and locked Domain Pack assets.
- Keep all provider output at `PROPOSAL_ONLY`; core code owns normalization and identifiers.
- Require explicit human decisions before producing a new, separated `READY_FOR_COMPILATION` package.
- Defer translation into authoritative compiler inputs and semantic artifacts to Prompt 5.

This approach is reversible: the Prompt 4 routes and Catalog additions can be removed without mutating historical Domain Packs or changing legacy contract bytes.
