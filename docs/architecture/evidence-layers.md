# Evidence Layers

## Modeling Evidence

Modeling evidence supports schema and mapping decisions:

- Why a Class exists
- Why a Property exists
- Why a Domain or Range was chosen
- Why a terminology alignment was accepted
- Why a field maps to a term
- Why a Schema Delta was accepted
- Why a SHACL constraint exists

Typical sources:

- Regulations
- Industry standards
- TM Forum documents
- Existing ontologies
- Domain reports
- Competency Questions
- Domain-expert decisions
- Modeling resolutions
- Local extension notes

## Business Fact Evidence

Business fact evidence supports concrete ABox assertions:

- A phone number belongs to a subscription
- An account has a status
- A contract has an end date
- A relation appears in an input record

Typical sources:

- JSON record
- JSON Pointer
- Source system
- Record identifier
- Field value hash
- Source timestamp
- Business document

## Common provenance

Future provenance may use PROV-O concepts such as:

- `prov:Entity`
- `prov:Activity`
- `prov:Agent`
- `prov:wasDerivedFrom`
- `prov:wasGeneratedBy`
- `prov:wasAssociatedWith`

Constraints for this repository:

- Do not depend on runtime remote downloads of PROV-O
- Do not treat PROV-O as a substitute for the MNP domain ontology
- Do not modify formal TTL modules in Stage 02 for provenance scaffolding

## Evidence is not confirmation

```text
presence of evidence ≠ confirmed
high confidence ≠ confirmed
automatic rule match ≠ confirmed
```

Evidence informs review. Only ReviewDecisionLog and ConfirmedModelingPackage
create formal decisions.
