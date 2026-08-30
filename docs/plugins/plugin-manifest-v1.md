# PluginManifest and PluginSnapshot v1

`PluginManifest` is a closed Draft 2020-12 capability declaration. It binds a
lowercase kebab-case plugin ID, API/plugin versions, installed distribution and
entry point, kinds/capabilities/media patterns, deterministic mode, side-effect
classes, implementation files, optional configuration schema and requirements.
Paths are distribution-relative POSIX paths: absolute, drive, UNC, empty and
`..` paths fail closed. Configuration schemas are UTF-8 JSON, digest-bound and
may not contain remote `$ref` values.

`PluginSnapshot` recomputes:

- raw and semantic manifest SHA-256;
- a canonical digest of every declared implementation file and relative path;
- distribution name/version and entry-point identity;
- configuration semantic SHA-256; and
- capabilities, determinism and side effects.

The snapshot ID is a stable URN over canonical content. It contains no current
time, absolute path, hostname or username. Any manifest, implementation,
distribution-version or configuration change invalidates verification.

A snapshot is reproducibility evidence. It is neither a cryptographic code
signature nor proof that installed Python is safe.
