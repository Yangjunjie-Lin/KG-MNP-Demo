# Demo walkthrough

## Expected decisions

| Case | Decision | Notes |
|------|----------|-------|
| CASE-01 | ELIGIBLE | All evidence valid and checks pass |
| CASE-02 | BLOCKED | Outstanding balance only |
| CASE-03 | BLOCKED | Active contract; full evidence/rule/clause/action |
| CASE-04 | BLOCKED | Billing + contract; two traces |
| CASE-05 | MANUAL_REVIEW | Expired billing evidence |
| CASE-06 | BLOCKED under rule 1.1 | Historical v1.0 assessment marked for reassessment |

## Commands

```bash
python scripts/showcase_demo.py
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli trace --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli run-all --backend rdf
pytest
```

离线演示默认使用 RDF。详见 `docs/local_showcase.md`。

## Protégé

Open `ontology/mnp-core.ttl` then optionally `mnp-compliance.ttl`. Alignments are optional.
