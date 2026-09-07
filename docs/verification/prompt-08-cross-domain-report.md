# Prompt 8 cross-domain validation report

Decision: **NOT_COMPLETED — backend gate failed**. Existing core fixtures and
pack validation are not a substitute for independent HTTP/browser artifacts.

| Acceptance level | Minimal | MNP | Forestry |
| --- | --- | --- | --- |
| Pack validated/discoverable | Existing EXPERIMENTAL 0.1.0 validated through service discovery | Existing 1.0.0 validated through discovery | Existing PLANNED 0.1.0; not promoted to usable capability |
| Ingestion executed (P8 independent workflow) | NOT_RUN | NOT_RUN | NOT_RUN |
| Evidence closed | NOT_RUN | NOT_RUN | NOT_RUN |
| Modeling executed | NOT_RUN | NOT_RUN | NOT_RUN |
| Review completed | NOT_RUN | NOT_RUN | NOT_RUN |
| Compilation validated | NOT_RUN through P8 API | NOT_RUN through P8 API | NOT_RUN |
| Package verified | NOT_RUN through P8 API | NOT_RUN through P8 API | NOT_RUN |
| Release verified | NOT_RUN through P8 API | NOT_RUN through P8 API | NOT_RUN |
| Browser workflow passed | NOT_RUN | NOT_RUN | NOT_RUN |

The retained P7 core lifecycle E2E does compile/verify a real Minimal package,
release, activate and explicitly roll back through core APIs. Its serial test
receipt is reported as **core regression**, not new Workbench acceptance.

No pack is modified on this partial branch. Historical digests remain:

- minimal: `9243d8a995a4a87b8d2048bf7cb0069203e3d7d528e57409e6d3f985ac11e014`
- mnp: `2554d6d4bbd98b4defd2a46243d6f4f01842320bcc929aff0a3a03ba7cc6ddd1`
- forestry 0.1.0: `58dbf2ab75189ecefdaf79e6c5e49ae7c796471e9be65aa48cbf0e21a21d66e9`

The explicitly authorized forestry 0.2.0 synthetic tree/inspection example is
**not implemented**. There is no new forestry lock/digest, synthetic fixture,
CQ oracle, mapping/evidence experiment, negative-case report or fourth-pack UI
smoke. No claim of real forestry data, field pilot, expert review or business
effect is made. Historical portable package compatibility is left to retained
core regression, not inferred from listing a pack.
