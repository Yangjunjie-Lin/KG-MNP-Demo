.PHONY: install test test-neo4j run-all validate-case03 evaluate-case03 trace-case03 docs check-refs neo4j-up neo4j-ping api frontend fullstack verify-frontend verify-fullstack verify-storage-atomicity verify-docker-runtime verify-repo-hygiene verify-stage-gate

install:
	python -m pip install -e ".[dev,api]"

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

api:
	python -m uvicorn kg_mnp_demo.api.app:app --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort

fullstack:
	python scripts/run_fullstack.py

verify-repo-hygiene:
	python scripts/check_repo_hygiene.py

verify-frontend:
	cd frontend && npm ci && npm run api:check && npm run verify

verify-fullstack:
	python scripts/check_repo_hygiene.py
	python -m pytest -q
	python scripts/check_references.py
	python scripts/check_rule_versions.py
	python scripts/check_openapi_drift.py
	$(MAKE) verify-frontend
	cd frontend && npx playwright install chromium
	python scripts/run_fullstack.py --reset-seed --playwright
	docker compose -f docker-compose.fullstack.yml config
	docker compose -f docker-compose.fullstack.yml build

verify-storage-atomicity:
	python -m pytest -q tests/storage/test_storage.py tests/storage/test_force_recompute_artifacts.py

verify-docker-runtime:
	python scripts/verify_docker_runtime.py

verify-stage-gate:
	python scripts/check_repo_hygiene.py
	python -m pytest -q
	python scripts/check_references.py
	python scripts/check_rule_versions.py
	python scripts/check_openapi_drift.py
	cd frontend && npm ci
	cd frontend && npm run api:check
	cd frontend && npm run verify
	cd frontend && npx playwright install chromium
	python scripts/run_fullstack.py --reset-seed --playwright
	python scripts/verify_docker_runtime.py
