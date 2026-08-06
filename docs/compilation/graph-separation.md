# Graph Separation

The dataset has stable named graphs derived from the package hash:

* the business ABox contains only confirmed business facts and its ontology
  header;
* the modeling provenance graph contains candidate, mapping, source-field,
  modeling-evidence, confidence, and axiom records;
* the review audit graph contains reviewer/session/decision data and all
  rejected or deferred items.

Metadata is never copied into business entity properties.
