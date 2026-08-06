# SHACL Validation

Stage 06 uses the frozen `foundation-instance` profile from
`shapes/foundation-instance-shapes.ttl`. Profiles are copied with LF-normalized
source bytes and hashes into the compilation directory. pySHACL runs offline
with RDFS inference, `advanced=false`, `js=false`, and no automatic repair.

Raw result blank-node identities are discarded. Results are projected to stable
semantic result IDs and deterministically serialized as JSON and N-Triples.
Violations block compilation; warnings and infos are recorded.
