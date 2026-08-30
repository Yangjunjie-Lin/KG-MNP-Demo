# Evidence-bound KG-IR v1

KG-IR means Knowledge Graph Intermediate Representation. It is a deterministic
transport for later modeling proposals; it is not a knowledge graph, ontology,
Confirmed Modeling Package or reviewed fact.

Items may be documents, text blocks, structured records, scalar fields, tables,
rows/cells, document metadata, image metadata or audio metadata. Payloads are
closed structures. Scalars retain original/normalized lexical forms and only
the non-domain types string, integer, decimal, boolean and null.

Every item, including each document root, has EvidenceRecord references.
Datasets close parents, evidence, transformations and PluginSnapshots, sort all
sets deterministically, and bind ProjectLock, SourceBatch, IngestionPlan,
QualityReport and ArtifactManifest. Ontology class/property/relation/instance,
business-object and confirmed-fact kinds are prohibited by schema and code.

`kg-mnp ir trace` follows item → evidence → locator → SourceAsset/blob hash →
PluginSnapshot → TransformationRecord without inventing a semantic mapping.
