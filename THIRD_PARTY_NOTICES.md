# Third-party license notices (summary)

This file summarizes licenses of third-party software referenced or depended upon by KG-MNP Demo.

| Component | License | Role |
|-----------|---------|------|
| RDFLib | BSD-3-Clause | Runtime dependency |
| pySHACL | Apache-2.0 | Runtime dependency |
| OWL-RL | W3C Software Notice / BSD-style | Runtime dependency |
| PyYAML | MIT | Runtime dependency |
| jsonschema | MIT | Runtime dependency (JSON input validation) |
| pandas | BSD-3-Clause | Optional modeling-analysis field statistics |
| NetworkX | BSD-3-Clause | Optional modeling-analysis task dependency checks |
| FlagEmbedding | MIT | Optional BGE embedding/reranking adapters; no weights redistributed |
| FAISS | MIT | Optional normalized dense-vector retrieval |
| Transformers / Tokenizers | Apache-2.0 | Optional local-only Fast Tokenizer loading |
| pypdf | BSD-3-Clause | Optional PDF text extraction dependency |
| openpyxl | MIT | Optional read-only XLSX parsing dependency |
| python-docx | MIT | Optional DOCX paragraph/table parsing dependency |
| Pillow | HPND | Optional image metadata parsing dependency |
| defusedxml | PSF-2.0 | Optional defensive Office XML parsing dependency |
| pytest | MIT | Dev/test dependency |
| Point-Topic CTO | GPL-3.0 | Conceptual reference only (not copied) |
| TM Forum Open API mirrors | Apache-2.0 | Schema mapping reference only |
| Protégé | BSD-2-Clause | Optional development tool |
| WIDOCO | MIT / Apache-2.0 (upstream) | Optional documentation tool |

The ingestion document dependencies are installed only through the bounded
`ingestion-documents` extra; no third-party binaries or model weights are
redistributed in the wheel. Full texts for runtime PyPI packages should be
obtained from installed distribution metadata (`pip show` / package `LICENSE`
files). CTO OWL files are intentionally **not** redistributed here.

Model licenses depend on the explicitly selected model ID and revision. Qwen,
BGE-M3 and BGE-reranker names in the method registry are not grants to redistribute
weights. Review the selected model card/license during explicit preparation.
The five-stage teaching materials are user-supplied synthetic references, not
third-party employee records or live model/review evidence.
