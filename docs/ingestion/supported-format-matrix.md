# Supported format matrix

| Format | Prompt 3 behavior | Honest limitation |
|---|---|---|
| TXT | UTF-8/BOM lines with line locators | No language or entity inference |
| Markdown | Heading/list/paragraph/code classification | HTML/links are not executed or fetched |
| JSON | Duplicate-safe, bounded, Decimal-preserving leaf values | No date/unit/domain inference |
| CSV/TSV | Deterministic delimiter, cell locators, formula-like warnings | Formula text is never executed |
| XLSX | Read-only cells/sheets and formula text | No macro/formula execution or cached-result authority |
| DOCX | Paragraph and table-cell extraction | Images/embedded content are not OCR'd/executed |
| PDF | Page text with page locators | Scanned pages need OCR; text ordering may require review |
| PNG/JPEG/GIF/TIFF | Format, dimensions, mode and safe metadata | Metadata-only; no OCR/classification/vision |
| WAV | Container/sample metadata and duration | Metadata-only; no speech recognition |
| Video | Source registration and missing-provider issue | No content understanding or fabricated text |
| Other audio | Source registration and missing-provider issue | No ASR or transcoding |

Optional document providers require the bounded `ingestion-documents` extra.
When absent, discovery reports `MISSING_DEPENDENCY`; core TXT/JSON/CSV and plugin
listing remain importable.
