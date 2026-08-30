# Project Manifest v1

`project.yaml` selects exact Domain Pack IDs and versions, required capabilities
and optional entrypoint names. The primary pack and every profile must reference
a declared pack; profiles select manifest entrypoints rather than filesystem
paths. Pack selections and profile entrypoints are sorted and unique.

The only Prompt 2 settings are `offline_only: true` and
`strict_validation: true`. Plugin/provider configuration belongs to Prompt 3.
Secrets, licenses, local roots, usernames, machines and arbitrary bypass paths
are not representable. The Domain Pack root is an explicit runtime resolver
input and is never persisted in the manifest.

