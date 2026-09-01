# `.kgop` Archive Format v1

`.kgop` is a deterministic ZIP of one verified package directory. Entries are
sorted POSIX paths with timestamp 1980-01-01 00:00:00, fixed regular-file mode,
fixed DEFLATE level, and no directory, symlink, absolute or traversal entry.
Verification rejects duplicates, metadata drift, zip slip, excessive
uncompressed size and compression ratio. The archive is outside Package Lock,
so export receipts may contain operational path/time without altering semantic
identity.
