# TBox / ABox Boundary

## TBox

TBox contains schema-level ontology constructs:

- Classes
- Object Properties
- Datatype Properties
- SubClassOf
- EquivalentClass
- Disjointness
- Domain
- Range
- Inverse Properties
- OWL restrictions
- Stable schema-level annotations

## ABox

ABox contains instance-level assertions:

- Concrete individuals
- Individual types
- Concrete datatype values
- Concrete object relations
- Concrete business facts
- Concrete business evidence bindings

## Dataset Modeling mode

Default run shape:

```text
CleanedPartialData
→ field profiles
→ instance proposals
→ relation proposals
→ mapping proposals
→ missing / conflict / ambiguity items
```

Default prohibitions:

- Must not modify TBox
- Must not add formal Classes
- Must not add formal Properties
- Must not add formal OWL restrictions
- Must not mint formal Schema from a single source field

Example:

```json
{
  "temporary_campaign_code": "ABC"
}
```

Allowed outputs:

- Candidate datatype property
- Candidate mapping
- Review item
- Local ABox property suggestion

Forbidden output:

- Automatic formal TBox property

## Ontology Release mode

Only an explicit Confirmed Schema Delta may produce:

```text
Frozen TBox Baseline
+ Confirmed Schema Delta
→ New TBox Version
```

Schema Delta requirements:

- Explicit reviewer
- Explicit rationale
- Explicit source
- Explicit target module
- Explicit compatibility impact
- Explicit version impact
- Explicit `publication_scope = TBOX`

## Absence principles

```text
absence ≠ false
missing ≠ rejected
unknown ≠ not exists
not observed ≠ negated
```

If `contract_end_date` is absent, the only valid reading is
`contract_end_date missing`. It does not mean the contract does not exist, that
the contract has ended, or that an eligibility condition is satisfied.
