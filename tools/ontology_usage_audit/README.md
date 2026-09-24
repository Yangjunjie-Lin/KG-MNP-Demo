# Benchmark / Prompt Token audit programs

This directory contains a portable distribution of the existing read-only
audit program and its pinned extraction dependency. Distribution-only changes
cover paths, import/style cleanup, equivalent UTC aliases, and explicit safe
exception handling. The accounting logic is unchanged. It does **not** contain
a budget ledger, API key, authorization grant,
raw model request/answer, benchmark prediction, score, or running process.
The original live workspace and its frozen controller remain untouched.

## JSON CLI (Python 3.12+, standard library only)

```powershell
python tools/audit_ontology_tokens.py snapshot --workspace PATH_TO_EXISTING_BENCHMARK_WORKSPACE
python tools/audit_ontology_tokens.py snapshot --workspace PATH_TO_EXISTING_BENCHMARK_WORKSPACE --revision r8luna --job-id ORIGINAL_JOB_ID --output NEW_REPORT.json
python tools/audit_ontology_tokens.py watch --workspace PATH_TO_EXISTING_BENCHMARK_WORKSPACE --output-dir runtime_reports/token-audit-observer --interval 30
```

The workspace must contain the original benchmark `budget.sqlite`,
`jobs.sqlite` and retained request/response/source-lock artifacts.
Those local inputs are deliberately not distributed. Snapshot stdout is one
JSON document; watch stdout is JSONL. Watch also maintains `latest.json` and
one atomic cumulative JSON view per original job in `runs/`.
Do not add together successive cumulative updates for the same job.
The independent observer does not dispatch jobs, call a model, or edit either database.

Each call, step, and job reports input/output/total tokens and known/unknown
coverage. `usage_category` distinguishes modeling, diagnostic testing, and
unclassified purposes. `execution_context` independently records benchmark
or diagnostic context; generation within a benchmark is not a production run.
Unknown usage remains null. Reservations/charges are never actual usage.
Failed calls/retries/interrupted unknown outcomes remain in the totals.
S2/S3 use captured requests and verified frozen-source signatures; direct
baselines remain DIRECT and unrecognized steps remain UNKNOWN.

## Source bundles and historical provenance

- `token-audit-portable-v1/`: JSON snapshot/watch implementation, synthetic
  tests, usage README, a new distribution freeze, and historical source-origin metadata.
- `token-report-portable-v1/`: extraction helpers, synthetic tests and the
  optional workbook builder. JSON auditing needs no spreadsheet library.

The original freeze is preserved as `source-origin.json`, with its historical
meaning and bytes. It does not attest the modified distribution sources or
authorize another experiment. A new `freeze.json` pins this distribution.
Historical test outputs and runtime data remain local and are not shipped.
`.gitattributes` prevents Git line-ending conversion of these byte-pinned
bundles, so a fresh checkout preserves the new helper and program hashes.
The wrapper above is the public entry point; no runtime source directory is
required to import or test it.

Run offline tests:

```powershell
python -m pytest tools/ontology_usage_audit/token-audit-portable-v1/test_audit_tokens.py tools/ontology_usage_audit/token-report-portable-v1/test_export_usage.py tests/upgrade/test_ontology_token_audit_entrypoint.py
```

Optional workbook generation requires a separately available
`@oai/artifact-tool` Node environment. No proprietary dependency, node_modules,
rendered spreadsheet or report snapshot is vendored:

```powershell
node tools/ontology_usage_audit/token-report-portable-v1/build_report.mjs PATH_TO_EXTRACTOR_SNAPSHOT.json PATH_TO_NEW_OUTPUT_DIRECTORY
```

The workbook consumes the older `export_usage.py` snapshot schema, not the new
`ontology-token-usage/1.0` JSON. Create that input with its explicit
`--workspace / --revision / --output` arguments. Full quality scores, effects,
95% CIs and external evaluator/license blockers are separate from token auditing.
