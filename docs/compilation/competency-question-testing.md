# Competency Question Testing

Prompt 5 executes only registered ASK, SELECT or CONSTRUCT query bytes. It does
not derive SPARQL from natural language. UPDATE-family operations, SERVICE,
remote dataset clauses and unsafe functions are rejected before an isolated
child process runs with size/result/time/path-depth limits. `PASSED` requires
an explicit oracle and every assertion to pass; no-oracle execution is
`UNVERIFIED`, and Prompt 4 structural coverage is not an execution result.
