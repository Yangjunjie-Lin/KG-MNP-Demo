# Recorded Model Output

The recorded provider imports UTF-8 JSON bytes produced elsewhere. Prompt 4
does not call a model API and exposes no API-key option. The raw response is
untrusted, bounded by bytes and JSON depth, and may contain only
`candidate_drafts`. Authority fields, final IDs, confirmation/review claims,
locks, code, RDF, paths, and secrets are rejected before normalization.

`ModelInvocationRecord` binds provider/model identity and revision, request and
response artifact references and SHA-256 hashes, prompt-template identity,
declared sampling parameters and seed, determinism class, finish/parse status,
issues, and a semantic digest. Exact request/response bytes can be reverified
against the record. `RECORDED_BYTES_ONLY` means the captured bytes are stable;
it does not mean the external model call is reproducible, correct, or
semantically authoritative.

Use `kg-mnp model provider-request export` and
`kg-mnp model provider-response import --provider recorded-model-output-provider`.
Both operations are offline.
