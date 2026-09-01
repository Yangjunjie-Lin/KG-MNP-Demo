# SHACL Compilation

The compiler supports Node/Property Shapes, cardinalities, datatype/class,
node-kind and in-values constraints. Paths are direct IRIs, list nodes are
structural skolem IRIs, and `minCount <= maxCount`. Baseline, compiled and
effective shapes remain separate. SHACL-SPARQL, JavaScript, custom functions,
remote imports and arbitrary paths are prohibited.

Some locked historical baseline packs contain SHACL-SPARQL. Their original
asset bytes and lock records remain untouched and are included in the package,
but Prompt 5 never executes those components. The deterministic
`SAFE_SHACL_CORE_PROJECTION` excludes each executable connected shape component
from the effective validation graph and records baseline, effective, and
excluded counts in the compilation report. Any newly confirmed Prompt 5 shape
that uses SHACL-SPARQL, JavaScript, custom functions, remote imports, or an
arbitrary path still fails closed; the projection is a compatibility boundary
for locked baseline assets, not an escape hatch for new constraints.
