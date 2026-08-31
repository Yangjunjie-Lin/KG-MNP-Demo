# ADR-0004: Evidence-Grounded Ontology Modeling and Human Review

- Status: Accepted
- Date: 2026-08-31
- Decision scope: Prompt 4 control plane

## Context

Prompt 3 produces evidence-bound KG-IR from untrusted source content. KG-IR is
an intermediate observation model: parser output can be incomplete, ambiguous,
or wrong, and source text may contain prompt injection. Treating it as an
ontology would collapse evidence, interpretation, human authority, formal
validation, and publication into one unsafe step.

The retained ModelingProposal/ReviewDecisionLog/ConfirmedModelingPackage 1.0
family is primarily ABox-oriented, predates Prompt 3 evidence closure, and is
already consumed by a legacy compiler. Expanding those stable contracts in
place would change their meaning and let old code encounter TBox, Mapping, or
SHACL structures it does not validate.

## Decision

1. Modeling starts only from a human-approved immutable Scope. Scope fixes the
   domain, target partitions, namespaces, prohibited operations, and acceptance
   gates; a mutation makes approval stale.
2. Competency Questions are recorded before modeling so requirements and later
   validation intent remain inspectable. Prompt 4 measures only structural
   coverage.
3. A read-only snapshot of locked local Domain Pack ontology assets is indexed
   before proposals. Baseline reuse is preferred and explicit because silently
   duplicating established terms weakens interoperability and review.
4. Modeling providers have `PROPOSAL_ONLY` authority. They return bounded
   drafts, never final candidate IDs, review states, confirmation states,
   semantic files, or publication operations. Core revalidates and computes
   identity.
5. A new Prompt 4 Contract family is added alongside byte-identical legacy
   contracts. The old APIs, CLI route, compiler, and regressions remain intact.
6. Recorded Model Output imports exact untrusted bytes and a
   ModelInvocationRecord. It is not a live LLM integration and recorded bytes
   do not make an external model invocation reproducible.
7. Formal prevalidation checks structural, closure, namespace, conflict,
   resource, and authority properties. It is not OWL consistency reasoning,
   SHACL execution, CQ execution, or a semantic-accuracy judgment.
8. Every candidate requires explicit human review. Scores and provider
   agreement cannot bypass roles, quorum, append-only logs, evidence, or stale
   protection. Modifications create new Core-owned candidate revisions.
9. Finalization creates only a deterministic
   `READY_FOR_COMPILATION` Confirmed Modeling Package. It contains closed JSON
   candidates and no RDF/OWL/SHACL, compiler execution, publication, registry,
   or GraphDB instruction.
10. Deterministic semantic compilation and final OWL/SHACL/CQ/provenance
    validation are deferred to Prompt 5, where the new package can be consumed
    deliberately without changing the legacy compiler contract.

## Alternatives considered

- Direct KG-IR-to-RDF generation was rejected because parser observations and
  hostile source text would acquire semantic authority without review.
- Extending the 1.0 modeling contracts in place was rejected because it breaks
  stable consumers and obscures the compiler migration boundary.
- Confidence-based auto-approval was rejected because similarity and provider
  scores are ordering evidence, not calibrated semantic correctness.
- A live default LLM provider was rejected because network/model/version/prompt
  state would not be closed, and API credentials would enter the threat model.
- Letting providers mint final IDs was rejected because provider-specific
  formatting and hostile fields would control authoritative identity.
- Compiling inside finalization was rejected because review and compiler
  authority require independently verifiable artifacts and failure domains.

## Consequences

The system gains explicit requirements, baseline reuse, evidence closure,
provider provenance, deterministic merging, review replay, and a stable Prompt
5 handoff. The cost is more artifacts, explicit decisions, reviewer time, and a
temporary coexistence of legacy and Prompt 4 contract families. Prevalidation
cannot substitute for a reasoner, and recorded providers cannot prove model
reproducibility or quality.

## Risks

Python plugins remain trusted installed code rather than an OS sandbox.
Upstream PDF/KG-IR quality can limit candidates. Lexical alignment can be
misleading across languages. Large ontologies and review queues need further
performance measurement. Platform symlink and optional parser behavior remain
covered by platform-specific tests but can vary operationally.

## Migration

Prompt 4 adds Catalog entries, Plugin API 1.1, the new control plane, and
`model`/`review` routes while retaining all Prompt 3 schema/plugin/pack bytes.
Projects relock the new Catalog explicitly; old locks become stale rather than
being ignored. Prompt 5 will add an explicit deterministic adapter/compiler for
the new confirmed package.

## Reversibility

Because historical contracts and Domain Packs are not mutated, the new routes,
schemas, and providers can be removed together and the Catalog regenerated
without rewriting retained artifacts. Published ontology and registry state is
untouched by this decision.
