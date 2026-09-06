# Package and release state separation

Package records remain `VALIDATED_UNPUBLISHED` after import.  Registry import is
`IMPORTED_VERIFIED`; only controlled publication creates `RELEASED`; an
environment pointer independently records control-plane selection.
