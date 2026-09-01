# Prompt 5 Compilation Baseline Audit

Prompt 5 started from `codex/ontology-modeling-review-p04` at
`eccc5092831503974c8aa54f158e6674445b1cb4`. The initial tree was clean and
the historical tag resolved to
`e45da340267de8d4b7b3a54177822aa641e3a601`. The full Prompt 4 regression,
Stage 06, Application Phase 06 offline suite, Ruff, and the full pytest suite
passed before modification. Raw command output is local-only under
`runtime_reports/refactor/prompt-05/`.

## Contract and authority baseline

- One public Catalog contained 59 schemas at schema version 1.1.0. Its
  semantic digest was `d44ff7a306ecba354a96346d9e80a48c6f271bb6ed65589f6eef8a927d342620`.
- The Catalog Lock was
  `urn:kg-mnp:contract-catalog-lock:c102580e821be622a38e55d13dd726215796caafb5621af8e0c5623a3de1e76b`.
- Project Locks bind the Catalog digest and exact Domain Pack Locks. A Catalog
  migration therefore makes historical Prompt 4 workspaces stale; no artifact
  is rebound or edited in place.
- The Prompt 4 confirmed-package contract is the only new compiler input. It
  binds Scope/Approval, CQ/coverage, KG-IR/evidence, baseline, terminology,
  alignment, mappings, proposal/prevalidation, review policy/log, provider
  snapshots, four candidate partitions, and closure results.
- Candidate identity is recalculated from the typed semantic body. The actual
  union contains 7 TBox, 6 Mapping, 4 ABox, and 8 SHACL types, with the five
  actions `REUSE_EXISTING`, `CREATE_NEW`, `ALIGN_TO_EXISTING`, `ASSERT`, and
  `CONSTRAIN`.

## Stage 06 classification

| Module | Classification | Prompt 5 disposition |
|---|---|---|
| `rdf_canonical.py` | REUSE_AS_GENERIC_PRIMITIVE | Canonical NT/NQ moved to the domain-neutral primitive; Stage 06 is a compatibility wrapper with its historical readable prefixes. |
| `owl_consistency.py` | EXTRACT_TO_SEMANTIC_KERNEL / MNP_SPECIFIC | The pinned subprocess primitive is generic; the old MNP ontology loader and report remain in the wrapper. |
| `shacl_validation.py` | EXTRACT_TO_SEMANTIC_KERNEL / WRAP_FOR_LEGACY_COMPATIBILITY | New final SHACL gate uses the same deterministic-result principles with explicit Prompt 5 policy. |
| `compiler.py`, `abox_compiler.py` | OLD_CONTRACT_ONLY | Retained for historical ConfirmedModelingPackage 1.0 and Stage 06. |
| provenance/review audit | MNP_SPECIFIC | Retained; Prompt 5 uses PROV-O and a domain-neutral toolchain namespace. |
| candidate resolution, policy, contracts | OLD_CONTRACT_ONLY | Retained unchanged as the legacy control plane. |
| artifacts/manifest/identifiers | REUSE_AS_GENERIC_PRIMITIVE | Hash and deterministic-identity patterns reused; the ontology package format is new. |

The old compiler primarily compiles ABox, hardcodes the MNP ontology through
repository paths, uses an MNP provenance vocabulary, couples compilation to
publication, and has no generic CQ/package gate. It is not called by the new
control plane.

## Formal engine and supply-chain baseline

- ROBOT 1.9.7; JAR SHA-256
  `91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d`.
- Embedded HermiT dependency 1.4.5.456. The entry check ran with Java 23.0.2;
  CI uses a pinned supported Java runtime.
- The reasoner ran offline successfully before change. The JAR is an ignored
  local cache and is not shipped in the wheel.
- pySHACL 0.28.1; final execution fixes `advanced=False`, `js=False`,
  `do_owl_imports=False`, RDFS inference, and offline Meta-SHACL. SHACL-SPARQL,
  JavaScript and remote imports are rejected before execution.
- RDFLib 7.6.0, owlrl 6.0.2, jsonschema 4.23.0, and PyYAML 6.0.2 were present.

No generic CQ gate, portable ontology manifest/lock, or deterministic offline
archive existed at entry. RDFLib deprecation warnings concerning Dataset and
ConjunctiveGraph APIs and Starlette's multipart import warning were baseline
warnings, not suppressed outcomes.
