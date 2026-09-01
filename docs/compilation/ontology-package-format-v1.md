# Ontology Package Format v1

A portable package contains source authorities, byte-identical locked baseline
assets, canonical/readable ontology/data/shapes/provenance, MappingPlan, named
dataset, formal validation reports, manifest, lock, package validation and reproduction
reports. Its only Prompt 5 state is `VALIDATED_UNPUBLISHED`.

The lock separately binds the manifest and every payload path, media type,
size, byte hash, and semantic hash. It excludes itself and the archive. Strict
verification rejects missing/extra files, symlinks, traversal, absolute/Windows
paths, prohibited content and any byte/semantic mismatch. Registration,
release and activation belong to Prompt 6.

Package identity uses a two-pass, non-circular construction. A zero placeholder
first permits package-derived graph IRIs to be assembled. The final Package ID
binds the compilation plan, confirmed package, compiler snapshot, and a
normalized semantic payload digest over the effective TBox, ABox, compiled and
effective shapes, mapping/statement provenance, evidence lineage, review audit,
compilation activity, MappingPlan, CQ plan, input attestation, and locked
baseline asset semantics. Package-derived graph IRIs, the ontology-module
package reference, locks, manifests, and derived reports are excluded only to
avoid an impossible hash fixed point; the strict verifier reconstructs and
checks them independently.
