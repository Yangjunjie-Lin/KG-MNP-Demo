# Public Schema Catalog

`src/kg_mnp/contracts/catalog.json` lists each public name, version, `$id`,
package resource, scope, stability, authority level and raw SHA-256. Names,
identifiers, resource paths and name/version pairs are unique. The catalog
contains the nine Toolchain contracts and eleven byte-preserved Modeling
contracts; it is not duplicated in the Modeling compatibility package.

`catalog.lock.json` binds the exact catalog bytes, catalog semantic digest and
each schema digest. Its preimage is the lock object without `content_digest`
and `lock_id`. `content_digest` is the KG-MNP Canonical JSON v1 SHA-256 of that
preimage. `lock_id` is a stable URN derived only from `content_digest`. No time
or installation path participates. Run:

```text
kg-mnp contracts list --json
kg-mnp contracts show domain-pack-manifest
kg-mnp contracts verify-catalog
python scripts/generate_contract_catalog.py --check
```

The package uses `importlib.resources`; neither current directory nor a source
repository is required. Remote resolution is forbidden by construction.

