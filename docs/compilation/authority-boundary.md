# Stage 06 Authority Boundary

`ConfirmedModelingPackage` is the only semantic decision input accepted by the
formal compiler. The compiler independently reconstructs and validates the
package from CleanedPartialData, ModelingProposal, the final ReviewDecisionLog,
and all frozen dependencies before it emits any artifact. A proposal or review
log cannot be compiled directly, and a BLOCKED package is rejected.

The compiler is a deterministic representation step, not a new modeling
decision-maker. Rejected and deferred items are retained only in the review
audit graph. Reasoning and SHACL validate the asserted result and never write
back to it.

Both the compiler and reconstruction validator verify the supplied ontology
baseline against the current Stage 03 ontology files, module configuration,
term inventory, and reasoner attestation. This gate is part of the Python API,
not a CLI precondition. A stale or forged baseline fails before profiles are
loaded, SHACL or HermiT executes, or any artifact is written.
