# Historical MNP Eligibility Fixture

This fixture preserves the historical mobile-number-portability eligibility
contract as domain-specific regression input. It is not a standalone product,
the toolchain core, or a general ontology-engineering contract.

## Assets

- `schemas/mnp_case_input.schema.json`: the legacy Draft 2020-12 input contract;
- `shapes/eligibility-instance-shapes.ttl`: strict eligibility constraints;
- `../../shapes/foundation-instance-shapes.ttl`: the MNP foundation profile
  composed by the retained loader.

The schema identifier remains stable for historical compatibility. It must not
be reused as the future evidence-bound intermediate representation or Project
Workspace contract.

Related MNP fixtures now live under `../data` and `../inputs`; rules,
competency questions, queries, mappings, terminology, and ontology modules are
owned by the enclosing MNP Domain Pack. There is no duplicate top-level
authority location.

## Internal regression invocation

The public eligibility console script has been removed. Maintainers may invoke
the retained internal module while its relocation remains pending:

```bash
python -m kg_mnp.cli evaluate --case CASE-03 --backend rdf
python -m kg_mnp.cli trace --case CASE-03 --backend rdf
python -m kg_mnp.pipeline \
  --input domain_packs/mnp/fixtures/inputs/case03.json \
  --output-dir runtime_outputs/case03
```

Generated output belongs in ignored runtime directories and is never a golden
fixture merely because it was produced by this example.
