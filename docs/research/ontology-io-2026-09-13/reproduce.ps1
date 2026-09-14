# Run from the repository root. No credentials and no paid calls.
# Output directories must be new; do not erase older evidence to rerun.
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$ioRunSuffix = [guid]::NewGuid().ToString('N')
$ioWorkspace = "runtime_reports/ontology-io-reproduction-$ioRunSuffix"

python -m pip install -r config/ontology_io/scorer-requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Scorer dependency installation failed' }
python tools/prepare_ontology_benchmarks.py --benchmark llms4ol_2026 --with-data
if ($LASTEXITCODE -ne 0) { throw 'LLMs4OL resource preparation failed' }
python tools/prepare_ontology_benchmarks.py --benchmark cq4oe_0_0_1 --with-data
if ($LASTEXITCODE -ne 0) { throw 'CQ4OE resource preparation failed' }
# Explicitly reports BLOCKED_LICENSE_DATA_NOT_FETCHED; code/licence audit only.
python tools/prepare_ontology_benchmarks.py --benchmark oskgc --with-data
if ($LASTEXITCODE -ne 0) { throw 'OSKGC code/licence audit failed' }
python tools/prepare_ontology_benchmarks.py --benchmark onto_generation
if ($LASTEXITCODE -ne 0) { throw 'Paper resource audit failed' }
python tools/verify_ontology_io_evaluation.py --output "$ioWorkspace/engineering"
if ($LASTEXITCODE -ne 0) { throw 'Engineering verification failed; retain its logs' }
foreach ($ioPhase in @('smoke', 'pilot', 'full')) {
    python tools/run_ontology_benchmark_matrix.py --protocol config/ontology_io/protocols/full-local-holdout.yaml --phase $ioPhase --workspace "$ioWorkspace/matrix"
    if ($LASTEXITCODE -ne 2) { throw 'Expected explicit BLOCKED status (2); inspect receipt' }
}
# Resume verifies frozen configuration/source/resources/inputs and keeps both attempts.
python tools/run_ontology_benchmark_matrix.py --protocol config/ontology_io/protocols/full-local-holdout.yaml --phase full --workspace "$ioWorkspace/matrix" --resume
if ($LASTEXITCODE -ne 2) { throw 'Expected explicit BLOCKED status (2); inspect receipt' }
Write-Output "Evidence: $ioWorkspace; no LIVE predictions or comparative score generated."
