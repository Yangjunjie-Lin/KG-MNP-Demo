# Third-party license notices (summary)

This file summarizes licenses of third-party software referenced or depended upon by KG-MNP Demo.

| Component | License | Role |
|-----------|---------|------|
| RDFLib | BSD-3-Clause | Runtime dependency |
| pySHACL | Apache-2.0 | Runtime dependency |
| OWL-RL | W3C Software Notice / BSD-style | Runtime dependency |
| PyYAML | MIT | Runtime dependency |
| jsonschema | MIT | Runtime dependency (JSON input validation) |
| pytest | MIT | Dev/test dependency |
| Point-Topic CTO | GPL-3.0 | Conceptual reference only (not copied) |
| TM Forum Open API mirrors | Apache-2.0 | Schema mapping reference only |
| Protégé | BSD-2-Clause | Optional development tool |
| WIDOCO | MIT / Apache-2.0 (upstream) | Optional documentation tool |
| neo4j Python driver | Apache-2.0 | Optional Bolt client (`[neo4j]` extra) |
| neosemantics (n10s) | Apache-2.0 | Optional Docker plugin for RDF import |
| Neo4j Community (Docker) | GPL-3.0 (server) | Optional local graph DB via compose; not redistributed |

Full texts for runtime PyPI packages should be obtained from the installed distribution metadata (`pip show` / package `LICENSE` files). CTO OWL files are intentionally **not** redistributed here.
