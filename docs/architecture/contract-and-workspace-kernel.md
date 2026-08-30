# Contract and Workspace Kernel

The Prompt 2 kernel has three bounded layers. `kg_mnp.contracts` packages the
only public Catalog, offline registry, canonicalization, restricted document
I/O, stable reports and identifiers. `kg_mnp.domain_packs` indexes and verifies
data-only local knowledge packs. `kg_mnp.workspace` selects exact packs and
provides the filesystem and lock boundary consumed by later modules.

Resolution flows from ProjectManifest to a local DomainPackRegistry, through
the exact dependency closure, into verified Pack locks, then into ProjectLock.
The Catalog digest is bound at the same point. Every edge is deterministic and
offline; install locations and Workspace roots remain runtime inputs.

Authority does not flow from content identity. LLMs, Agents, plugins, Packs,
Workspaces and proposals remain non-authoritative. A later review flow may
produce a Confirmed Modeling Package, and only that confirmed input may enter
the compiler. Feedback becomes a proposal rather than a direct ontology edit.

Prompt 3 can consume Catalog APIs, Pack resolution and Workspace layout for a
Plugin SDK without creating another manifest family. Prompt 4 can write source
and evidence artifacts under their assigned directories. Later compiler,
package, diff, registry and UI work must reference these frozen contracts.

