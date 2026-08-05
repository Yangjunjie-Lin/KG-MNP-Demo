# CleanedPartialData

`CleanedPartialData` is a generic cleaned JSON envelope. Its `data` member may
be any JSON object or array; the central contract does not require subscriber,
account, billing, contract, phone-number, or eligibility fields.

The envelope separates four ideas:

- `sources` identifies business records, files, APIs, or documents without
  requiring a network-reachable locator.
- `field_metadata` points into `data` with exact RFC 6901 JSON Pointers and
  records source references, presence, and optional confidence.
- `declared_missing_items` names expected paths that do not exist.
- `declared_conflicts` preserves every alternative and its sources.

Presence values are `PRESENT`, `NULL`, `UNKNOWN`, and `REDACTED`. `MISSING` is
not a presence value because a missing field has no data member to annotate.
An explicit JSON `null` remains different from absence, unknown, redacted,
false, zero, and the empty string.

The six synthetic examples contain no real personal data and demonstrate the
supported edge cases.

