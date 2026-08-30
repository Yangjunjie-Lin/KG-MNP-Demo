# Minimal Prompt 3 ingestion project

These small, reviewed fixtures contain no personal data or semantic authority.
TXT, Markdown, JSON, and CSV are committed as plain source inputs. Generate the
optional XLSX, DOCX, PDF, PNG, and WAV fixtures in the ignored runtime area:

```console
python scripts/generate_ingestion_examples.py
python scripts/generate_ingestion_examples.py --check
```

The default output is `runtime_outputs/prompt-03-examples`. `--check` generates
the complete binary fixture set twice in isolated temporary directories and
requires byte-identical outputs. PNG and WAV ingestion is metadata-only. The
fixture generator does not create OCR, ASR, image-classification, or video
content claims.

## End-to-end CLI demonstration

Create a Prompt 2 workspace first, or substitute any already valid workspace.
The following PowerShell sequence then exercises the real artifact flow. JSON
output is used so deterministic identifiers can be passed to the next command.

```powershell
$workspace = 'runtime_outputs/prompt-03-demo-workspace'
kg-mnp workspace init $workspace --project-id prompt03-demo --project-version 0.3.0 `
  --display-name 'Prompt 3 Demo' --domain-pack minimal --domain-pack-version 0.1.0 `
  --domain-packs-root domain_packs
$sourceResult = kg-mnp source add $workspace examples/ingestion/minimal-project/sample.txt --json | ConvertFrom-Json
$sourceId = $sourceResult.result.source.source_id
$batchResult = kg-mnp source batch-create $workspace $sourceId --json | ConvertFrom-Json
$batchId = $batchResult.result.batch_id
$planResult = kg-mnp ingest plan $workspace --batch $batchId --json | ConvertFrom-Json
$runResult = kg-mnp ingest run $workspace --plan $planResult.result.plan_id --json | ConvertFrom-Json
$runId = $runResult.result.run.run_id
$datasetId = $runResult.result.dataset_id
kg-mnp ingest status $workspace $runId --json
kg-mnp ingest validate $workspace $runId --json
$dataset = kg-mnp ir inspect $workspace $datasetId --json | ConvertFrom-Json
$itemId = $dataset.result.items[0].item_id
kg-mnp ir validate $workspace $datasetId --json
kg-mnp ir sources $workspace $datasetId --json
kg-mnp ir trace $workspace $itemId --json
```

The trace ends at the SourceAsset content hash through a SourceLocator,
EvidenceRecord, TransformationRecord, and PluginSnapshot. It does not cross the
human-review or ontology-authority boundary.
