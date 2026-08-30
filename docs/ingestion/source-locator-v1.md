# SourceLocator v1

SourceLocator is a closed union of `whole-source`, `byte-range`,
`text-line-range`, `json-pointer`, `delimited-cell`, `delimited-range`,
`spreadsheet-cell`, `spreadsheet-range`, `document-paragraph`,
`document-table-cell`, `pdf-page`, `pdf-page-region`, `image-region` and
`time-range`.

Byte and millisecond ranges are zero-based, start-inclusive and end-exclusive.
Text/table/spreadsheet rows and columns and PDF pages are one-based and
inclusive. Document paragraph/table indexes follow the explicit fields in the
schema. Image/PDF regions use integer `x`, `y`, `width`, `height` from the
top-left origin. JSON Pointer follows RFC 6901, including `~0` and `~1` escapes.

Schema and semantic validation reject negative/zero coordinates where
forbidden, reversed or empty exclusive ranges, empty sheets, malformed
pointers, unknown kinds and non-finite numbers. Evidence closure reparses the
source and rejects out-of-bounds or hash-mismatched locators.
