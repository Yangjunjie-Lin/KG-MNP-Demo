# EvidenceRecord and TransformationRecord v1

Core creates every authoritative evidence and transformation ID. A plugin
cannot return `evidence_id`, KG-IR IDs or artifact paths through the SDK.

EvidenceRecord binds SourceAsset ID and byte hash, a SourceLocator, the hash and
media type of the observed value, the parser PluginSnapshot, transformation
IDs and quality flags. Whole-source evidence anchors every document root.
Verification closes Source, blob, snapshot and transformation references and
re-extracts the observed value through the locator.

TransformationRecord hashes original and normalized values, implementation and
configuration. Prompt 3 operations are representation-preserving NFC/newline,
BOM/string/Decimal preservation, delimiter decoding and structural flattening.
Unit conversion, domain coding, imputation, entity resolution and semantic
inference are absent. Potentially lossy operations would require explicit
configuration and review.

Evidence is a traceable observation, not confirmed knowledge, a business
object, an ontology instance or expert approval.
