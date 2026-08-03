# Demo Script (CASE-01 … CASE-09)

| Case | Eligibility | Process note |
|------|-------------|--------------|
| CASE-01 | ELIGIBLE | Can request auth code |
| CASE-02 | BLOCKED | Outstanding balance |
| CASE-03 | BLOCKED | Active contract |
| CASE-04 | BLOCKED | Multiple independent reasons |
| CASE-05 | MANUAL_REVIEW | Missing/expired evidence |
| CASE-06 | BLOCKED | Rule version update / reassessment |
| CASE-07 | ELIGIBLE | Auth code expired → cannot advance |
| CASE-08 | BLOCKED | Termination signed, not yet effective |
| CASE-09 | BLOCKED | Identity mismatch |

Run:

```bash
python scripts/seed_demo_data.py
pytest -q
```
