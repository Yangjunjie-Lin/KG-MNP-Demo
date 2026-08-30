# Structural quality gates v1

QualityReport measures source integrity, parse success, structural and locator
validity, evidence coverage, transformation traceability, normalization
consistency and content coverage. Measurement bases are exact structural,
coverage and policy checks. `GROUND_TRUTH_COMPARISON` is reserved for an actual
human gold dataset and is not emitted by the default builder.

`PASS` means hashes, parse, locators and all closures passed with no review
flags. `REVIEW_REQUIRED` covers image-without-vision, WAV-without-ASR, scanned
PDF, uncertain PDF text order, formula-like cells or other explicitly partial
semantics. `FAIL` covers hash/path/ZIP/contract/parse/artifact failures or
incomplete required closure.

Scores are basis points over declared structural numerators/denominators. They
are not OCR, ASR, semantic extraction or ontology accuracy.
