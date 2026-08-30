# Canonicalization and Digests

KG-MNP Canonical JSON v1 encodes UTF-8, sorts object keys, removes insignificant
whitespace, emits Unicode directly and rejects non-finite numbers. It is a
deliberately small profile, not an RFC 8785 claim. Semantic hashes are lowercase
SHA-256 over those canonical bytes.

A raw file hash covers exact bytes. A semantic hash covers parsed JSON/YAML
meaning and therefore ignores presentation such as mapping order. Locks record
both manifest file and semantic hashes. Domain Pack text is fixed to LF through
`.gitattributes`; this makes raw asset hashes stable across supported checkout
platforms without changing Prompt 1 semantic content.

Self-referential fields never enter their own digest. Catalog, Pack and Project
locks hash a documented core object, append `content_digest`, then mint a stable
URN from that digest. Wall-clock time, absolute roots, usernames and hostnames
are absent, so equivalent content in different directories yields equal locks.

