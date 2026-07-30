.PHONY: install test test-neo4j run-all validate-case03 evaluate-case03 trace-case03 docs check-refs neo4j-up neo4j-ping

install:
	python -m pip install -e ".[dev,neo4j]"

test:
	python -m pytest

test-neo4j:
	python -m pytest -m neo4j

run-all:
	python -m kg_mnp_demo.cli run-all --backend rdf

validate-case03:
	python -m kg_mnp_demo.cli validate --case CASE-03

evaluate-case03:
	python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend rdf

trace-case03:
	python -m kg_mnp_demo.cli trace --case CASE-03 --backend rdf

neo4j-up:
	docker compose up -d
	python -m kg_mnp_demo.cli neo4j-up

neo4j-ping:
	python -m kg_mnp_demo.cli neo4j-ping

check-refs:
	python scripts/check_references.py

docs:
	bash scripts/generate_docs.sh
