# Ontology glossary (MVP)

| Term | Meaning | Module |
|------|---------|--------|
| Subscriber | Party requesting MNP | IDENTITY |
| NaturalPerson / OrganisationSubscriber | Subscriber subclasses | IDENTITY |
| IdentityVerification | Real-name verification observation | IDENTITY |
| PhoneNumber | Masked number under assessment | IDENTITY |
| TelecomAccount / BillingAccount | Billing/customer account | ACCOUNT_BILLING |
| OutstandingBalanceObservation | Billing balance evidence subclass | ACCOUNT_BILLING |
| TelecomService / MobilePlan / ... | Catalogued service/offering reference | SERVICE_CONTRACT |
| ServiceSubscription | Instantiated subscription | SERVICE_CONTRACT |
| ServiceContract / CommitmentPeriod / TerminationAgreement | Contract that may block portability | SERVICE_CONTRACT |
| MNPCase / MNPRequest | Portability request case | PROCESS |
| ProcessStep / AuthorizationCode / ProcessEvent | Porting process artefacts | PROCESS |
| EligibilityAssessment | Deterministic evaluation episode | COMPLIANCE |
| assessmentTime | As-of datetime for rule-version selection and evidence validity | COMPLIANCE |
| EligibilityDecision | ELIGIBLE / BLOCKED / CONDITIONAL / MANUAL_REVIEW | COMPLIANCE |
| EvidenceRecord / SystemObservation / APIResponse | Provenanced observation with validity window | EVIDENCE_TIME |
| hasCaseEvidence | MNPCase → evidence available for that case | CORE |
| usesEvidence | EligibilityAssessment → evidence snapshot used in that evaluation | CORE |
| EligibilityRule / RuleVersion | Versioned operational rule | COMPLIANCE |
| BlockingReason | Independent failure/review reason | COMPLIANCE |
| RemediationAction | Recommended next step | COMPLIANCE |
| RegulatoryClause / Document | Regulatory grounding (demo clauses) | COMPLIANCE |
| AssessmentDependency | Explicit dependency on rule version/evidence | COMPLIANCE |
| MappingRecord | TMF→MNP mapping audit record | CORE |

Module catalog: `config/ontology_modules.yaml`.
