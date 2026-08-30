# Ingestion evaluation protocol

## Units and datasets

Evaluate on versioned, redistributable fixtures with exact byte hashes and a
declared format/feature matrix. Separate structural expectations (parse tree,
locator, closure) from any human semantic gold labels. Record toolchain wheel,
Python/platform, optional dependency versions, PluginSnapshots, policies and
finite limits. Do not include absolute paths or operation time in semantic
artifacts.

## Structural metrics

| Metric | Numerator / denominator |
|---|---|
| Source Registration Success Rate | safely registered fixtures / attempted fixtures |
| Parser Success Rate | structurally parsed supported fixtures / supported fixtures |
| Locator Validity Rate | re-extracted valid observations / evidence observations |
| Evidence Closure Rate | closed evidence records / evidence records |
| KG-IR Evidence Coverage | items with evidence / KG-IR items |
| Normalization Reproducibility | byte-identical normalized repeats / repeats |
| Plugin Selection Determinism | identical selections / equal plans |
| Artifact Reproduction Rate | byte-identical formal artifact sets / reproductions |

Processing time and peak memory are operational measurements and must report
hardware, platform, sample count and distribution; they do not enter artifact
IDs. At least two distinct absolute Workspace roots test path independence.

## Semantic metrics and claim boundary

Semantic accuracy is reported only when a named, versioned human ground-truth
dataset and comparison method exist. The structural evaluator does not emit
ground-truth accuracy. Prompt 3 supports claims about source/locator/evidence/
snapshot/transformation closure, deterministic provider selection and artifact
replay. It does not support claims about OCR, vision, ASR, relationship
extraction, ontology construction, cross-industry transfer or autonomous Agent
improvement.

Failures, warnings, skipped platform tests and optional prerequisites are part
of the report. `REVIEW_REQUIRED` is not counted as semantic success or failure
unless the evaluation protocol defines that classification in advance.
