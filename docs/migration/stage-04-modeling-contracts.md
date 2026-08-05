# Stage 04 Migration: Modeling Contracts and Proposal Generation

Stage 04 adds a central, review-only modeling path beside the retained legacy
eligibility example. The starting baseline was `main` at
`de3432d784e34dc2dcbd24698973554ee69858b4`, synchronized with `origin/main`
and with a clean initial worktree.

New controlled inputs are the frozen ontology baseline manifest, executable
mapping rules, terminology profile, and proposal policy in `config/modeling/`.
The baseline is rebuilt and verified against the unchanged Stage 03 ontology
release, reasoner attestation, term inventory, and module catalog.

The central CLI is `kg-mnp`; `kg-mnp-eligibility` remains the isolated legacy
CLI. The prior-stage boundary tests were advanced only where their historical
"Stage 04 absent" assertions would otherwise reject the authorized stage.
They continue to prohibit review automation, confirmed-package building,
compilers, GraphDB, WebVOWL, frontend, and HTTP API work.

Stage 04 produces deterministic JSON ModelingProposal artifacts. It does not
create ReviewDecisionLogs, ConfirmedModelingPackages, OWL, SHACL, RDF, or
database content. Stage 05 and later remain out of scope.

