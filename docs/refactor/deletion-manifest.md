# Prompt 1 Deletion Manifest

## Generated runtime artifacts approved for deletion

The following 11 tracked files are outputs from demo execution, not reviewed
golden fixtures. They are removed after this manifest is recorded; the baseline
Tag and Git history are the sole historical archive.

| Path | Category | Reason |
|---|---|---|
| `demo_outputs/README.md` | `GENERATED_RUNTIME_ARTIFACT` index | Describes generated output location rather than a product contract. |
| `demo_outputs/all_cases_summary.json` | `GENERATED_RUNTIME_ARTIFACT` | Run summary. |
| `demo_outputs/case03_assessment_validation.json` | `GENERATED_RUNTIME_ARTIFACT` | Run validation output. |
| `demo_outputs/case03_evaluation.json` | `GENERATED_RUNTIME_ARTIFACT` | Run evaluation output. |
| `demo_outputs/case03_inference.json` | `GENERATED_RUNTIME_ARTIFACT` | Run inference output. |
| `demo_outputs/case03_input_summary.json` | `GENERATED_RUNTIME_ARTIFACT` | Run input summary. |
| `demo_outputs/case03_input_validation.json` | `GENERATED_RUNTIME_ARTIFACT` | Run input validation output. |
| `demo_outputs/case03_trace.json` | `GENERATED_RUNTIME_ARTIFACT` | Run trace output. |
| `demo_outputs/case03_trace_subgraph.json` | `GENERATED_RUNTIME_ARTIFACT` | Run trace graph output. |
| `demo_outputs/case03_what_if.json` | `GENERATED_RUNTIME_ARTIFACT` | Run what-if output. |
| `demo_outputs/demo_report.html` | `GENERATED_RUNTIME_ARTIFACT` | Generated HTML report. |

## Retained artifacts

`tests/fixtures`, `tests/**/fixtures`, and `examples/**/expected` are
`REVIEWED_GOLDEN_TEST_ARTIFACT` locations. They are retained because tests use
them for deterministic reconstruction and regression comparison. Placeholder
`.gitkeep` files under controlled invalid-example directories are also retained.

## Repository-wide scan

No tracked files were found in `runtime_outputs`, `runtime_reports`, or
`runtime_logs`. Build directories, caches, local environments, browser output,
GraphDB data, downloaded tools, local databases, environment files, logs, and
license files are ignored and must remain untracked. The hygiene gate is
extended to enforce these rules and to reject secret-like file types/content.
