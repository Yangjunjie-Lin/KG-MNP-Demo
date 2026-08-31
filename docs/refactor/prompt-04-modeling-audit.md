# Prompt 4 Modeling Baseline Audit

## Audited baseline

- Source: `codex/plugin-ingestion-kgir-p03` at `52fb0bc064ed7a715ddc3269d23e89a1a78c917c`.
- Historical tag: `kg-mnp-phase06-baseline-2026-08-30` at `e45da340267de8d4b7b3a54177822aa641e3a601`.
- Public Contract Catalog: 34 entries, semantic digest `984c2031a36e6332c0c0a5724dc0dabbeb1f6f07f8389c3bda02e6744dccb5ed`.
- Catalog lock: `urn:kg-mnp:contract-catalog-lock:2f6a21f2533bf466437139cc0749dcfc43b6994ff0c8272d9918c7c45eb185be`.
- Plugin API: 1.0 with 13 built-in plugins. Discovery is metadata-only and external installed code is disabled by default.
- Prompt 3 evidence chain: `SourceAsset -> EvidenceRecord -> KGIRItem -> KGIRDataset`, with ArtifactReference/ArtifactManifest, Project Lock, and Domain Pack Lock binding.

The entry-gate commands and actual pre-change test logs are retained under the Git-ignored `runtime_reports/refactor/prompt-04/` directory. The initial worktree was clean. Prompt 1, Prompt 2, and Prompt 3 commits are ancestors of the target branch.

The migrated Catalog contains 59 entries and is locked by `urn:kg-mnp:contract-catalog-lock:c102580e821be622a38e55d13dd726215796caafb5621af8e0c5623a3de1e76b`; its semantic digest is `d44ff7a306ecba354a96346d9e80a48c6f271bb6ed65589f6eef8a927d342620` and lock digest is `f1dada64b4548a119041d93fbd03f32fc28474239c6f25185ddd2ee9e59fd836`. The 25 added resources are the 22 Prompt 4 modeling contracts and three compatible Plugin API 1.1 contracts.

## Existing modeling surface

The retained `kg_mnp.modeling` package implements deterministic legacy proposal generation, candidate identifiers, transformation semantics, review actions, review policy, review decision logs, confirmation, semantic validation, a legacy CLI route, and compiler-facing confirmed input. It is covered by the existing Stage 06 tests.

| Asset | Finding | Classification |
|---|---|---|
| ModelingProposal 1.0 | Primarily ABox-oriented; `schema_delta_candidates` is prohibited; input is cleaned-partial-data rather than KG-IR | SUPERSEDED_BY_NEW_CONTRACT_FAMILY |
| ReviewAction 1.0 | Closed decisions for the old candidate structure | RETAIN_BYTE_IDENTICAL |
| ReviewDecisionLog 1.0 | Hashes and decisions are coupled to legacy candidates and do not express the Prompt 4 queue, revisions, or conflict closure | SUPERSEDED_BY_NEW_CONTRACT_FAMILY |
| ConfirmedModelingPackage 1.0 | Some objects are broad and `publication_manifest` is not a closed compiler-only handoff for separated TBox/Mapping/ABox/SHACL candidates | COMPILER_ADAPTER_DEFERRED_TO_PROMPT_5 |
| MappingRules 1.0 | Domain-oriented deterministic mappings remain useful as controlled inputs | WRAP_WITH_NEW_CONTROL_PLANE |
| TerminologyProfile 1.0 | Retained domain terminology input, but it is not a multi-source terminology catalog or reviewed alignment set | WRAP_WITH_NEW_CONTROL_PLANE |
| OntologyBaselineManifest 1.0 | Retained release binding, but lacks a locked local import closure and searchable element indexes | WRAP_WITH_NEW_CONTROL_PLANE |
| Legacy compiler | Consumes legacy confirmed packages and cannot safely compile Prompt 4 TBox/Mapping/SHACL candidates | COMPILER_ADAPTER_DEFERRED_TO_PROMPT_5 |
| Domain assets | Locked semantic assets; no Prompt 4 mutation is authorized | DOMAIN_SPECIFIC |

## Safety conclusion

Prompt 4 must not reinterpret KG-IR as an ontology, promote provider output to confirmed authority, or change the legacy contracts in place. A new `modeling/control_plane` wraps retained services and creates proposal-only candidates, formal prevalidation, explicit human review, and a deterministic `READY_FOR_COMPILATION` package. Authoritative RDF/OWL/SHACL compilation remains deferred to Prompt 5.

## Final verification evidence

- The required post-change selection collected 240 tests: 238 passed, 2 Windows-platform tests skipped, and none failed or errored in 384.898 seconds.
- The final complete repository suite collected 1,348 tests: 1,339 passed, 9 platform-limited tests skipped, and none failed or errored in 5,751.182 seconds. The skips cover unavailable Windows symlink creation, POSIX execute-bit behavior, and POSIX FIFO behavior; Ubuntu CI retains those checks.
- The final Prompt 3 byte-preservation and historical Freeze selection passed 10/10 tests in 15.837 seconds. The protected tree remains 1,253 files with digest `b2f6e753171932aec8afe96ada74b3c9c4de77947f2b0e48031d5bb55403f5e1`.
- The final editable installation, repository-wide Ruff check, Prompt 4 contract generator check, Contract Catalog generator check, and `git diff --check` passed. Pip reported an environment-only dependency warning because the host `omniharbor-windows-agent` requires `httpx==0.28.1` while this project intentionally installs its declared `httpx==0.27.2` development dependency.
- `make verify-stage-06` passed in 5,284.28 seconds and `make verify-application-phase-06-offline` passed in 2,858.67 seconds. Their warnings are upstream `rdflib` deprecations plus Starlette's pending `python_multipart` import deprecation; no warning was converted into a hidden failure.
- The final Wheel SHA-256 is `db6dbde0e342c0e5a5bf67233920309c4af239e18549bbe6245b0816cb56b3e9`; the final sdist SHA-256 is `f44f8689ad37a6a5194b718607bff6a4cb4431b16c99b2220ce01c7adaaca33d`. Archive inspection found 59 schemas, 17 built-in manifests, all 22 Prompt 4 modeling schemas, and no runtime Domain Pack, Runtime Output, cache, test-plugin fixture, Secret, or local absolute path.
- A fresh repository-external venv installed the Wheel and the independent provider Wheel. Catalog verification, plugin discovery, `model --help`, `review --help`, external-provider default disablement and explicit Conformance, Minimal Baseline construction, nine proposal-only candidates, and a socket-denied no-network probe all passed from installed package paths.
