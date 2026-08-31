# Prompt 4 Claim-Evidence Matrix

| Claim | Code | Contract | Test | Example | Status | Limitation |
|---|---|---|---|---|---|---|
| Approved Scope controls modeling | control_plane/scope.py | ontology-scope, ontology-scope-approval | modeling_scope | Minimal E2E | SUPPORTED | Scope approval is human-authored metadata, not identity proof |
| KG-IR is the only data input | input bundle and providers | modeling-input-bundle | modeling_control, E2E | Minimal E2E | SUPPORTED | Upstream parser quality remains inherited |
| Baseline reuse is explicit | baseline and reuse provider | baseline-snapshot, candidate-set | modeling_baseline/providers | Minimal/MNP smoke | SUPPORTED | No remote ontology discovery |
| Candidate evidence closure | normalizer/prevalidator | candidate-set, proposal | candidates/prevalidation/security | Minimal E2E | SUPPORTED | Domain-modeling evidence must still be reviewed |
| Locked local baseline closure | baseline and Domain Pack lock verifier | baseline-snapshot, domain-pack-lock | baseline tamper/forgery/remote-import tests | Minimal/MNP smoke | SUPPORTED | No remote ontology resolution or download |
| Deterministic candidate normalization | candidates.py | candidate-set | candidates/determinism | cross-directory fixture | SUPPORTED | Determinism is byte/semantic, not correctness |
| Provider outputs remain proposals | provider execution/security | provider-response | providers/security | recorded response | SUPPORTED | Python plugins are not an OS sandbox |
| Formal prevalidation | prevalidation.py | formal-prevalidation-report | modeling_prevalidation | Minimal E2E | SUPPORTED | Not an OWL reasoner, SHACL execution, or CQ execution |
| Human review traceability | review actions/log | review-action/decision-log | modeling_review/security | Minimal E2E | SUPPORTED | Human review has operational cost |
| Review replay | review/replay.py | review-decision-log | modeling_review | Minimal E2E | SUPPORTED | Stable reviewer identifiers are organizational controls |
| Confirmed package determinism | review/finalization.py | confirmed-modeling-package | confirmation/determinism | cross-directory fixture | SUPPORTED | Still not RDF/OWL/SHACL |
| No provider bypass | scope/provider/review gates | policy and response schemas | security | malicious fixtures | SUPPORTED | In-process plugin isolation is policy-based |
| No direct RDF publication | candidate closed structures | proposal/confirmed package | security/boundaries | Minimal E2E | SUPPORTED | Authoritative compilation is Prompt 5 |
| Wheel-independent Prompt 4 CLI | lazy legacy exports and root routes | packaged Catalog and schemas | wheel packaging and isolated probe | copied Minimal pack/source outside repository | SUPPORTED | Legacy Stage 04 operations still intentionally require their frozen repository assets |
| Live LLM provider | None | None | boundary tests | None | NOT_IMPLEMENTED | Recorded bytes only; no live network call |
| Semantic accuracy improvement | Evaluation protocol only | None | None | None | NOT_IMPLEMENTED | Requires an expert gold standard |
| Hallucination reduction rate | Evaluation protocol only | None | None | None | NOT_IMPLEMENTED | No fabricated percentage is reported |
| Full OWL consistency | Prompt 5 boundary | None | boundary test | None | NOT_IMPLEMENTED | Prevalidation is structural only |
| Final SHACL validation | Prompt 5 boundary | None | boundary test | None | NOT_IMPLEMENTED | Candidate structure only |
| CQ execution | Prompt 5 boundary | coverage report | coverage test | Minimal coverage | PARTIALLY_SUPPORTED | Structural coverage is not execution success |
| Cross-industry validation | Evaluation protocol | None | None | None | NOT_IMPLEMENTED | Minimal and MNP compatibility are not cross-industry proof |
| Forestry implementation | None | None | preservation test | None | OUT_OF_SCOPE | Forestry remains PLANNED |
| Automatic business object publishing | None | None | boundary test | None | OUT_OF_SCOPE | Publication belongs to later authority stages |
