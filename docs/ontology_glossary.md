# Ontology glossary (MVP)

| Term | Meaning |
|------|---------|
| Subscriber | Party requesting MNP |
| PhoneNumber | Masked number under assessment |
| TelecomAccount | Billing/customer account |
| TelecomService | Catalogued service/offering reference |
| ServiceSubscription | Instantiated subscription |
| ServiceContract | Contract that may block portability |
| MNPCase | Portability request case |
| EligibilityAssessment | Deterministic evaluation episode |
| assessmentTime | As-of datetime for rule-version selection and evidence validity |
| EligibilityDecision | ELIGIBLE / BLOCKED / CONDITIONAL / MANUAL_REVIEW |
| EvidenceRecord / SystemObservation | Provenanced observation with validity window |
| hasCaseEvidence | MNPCase → evidence available for that case |
| usesEvidence | EligibilityAssessment → evidence snapshot used in that evaluation |
| EligibilityRule / RuleVersion | Versioned operational rule |
| BlockingReason | Independent failure/review reason |
| RemediationAction | Recommended next step |
| RegulatoryClause / Document | Regulatory grounding |
| AssessmentDependency | Explicit dependency on rule version/evidence |
| MappingRecord | TMF→MNP mapping audit record |
