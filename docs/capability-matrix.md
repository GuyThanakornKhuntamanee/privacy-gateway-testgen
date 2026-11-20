# Capability matrix (schema 2.1)

This matrix describes what the repository actually renders and verifies in this
checkout. A "yes" means a unit test or a measured dataset report exercises it;
it is not a claim about a downstream gateway.

## File formats

| Format | Generate | Reopen | Verify | Thai | Mixed | Structure-aware | Optional dependency |
|---|---|---|---|---|---|---|---|
| TXT / MD | yes | yes | text span | yes | yes | line, section | no |
| LOG | yes | yes | text span | **no** (technical English) | **no** | line | no |
| CSV | yes | `csv` | cell | yes | yes | row, column | no |
| JSON | yes | `json` | JSON path | note + entities | note + entities | key | no |
| YAML / YML | yes | strict subset | YAML path | note + entities | note + entities | key | no |
| XML | yes | ElementTree | XML path | note + entities | note + entities | key | no |
| ENV / INI / CONF / TOML | yes | strict subset | key path | comments | comments | key | no |
| SQL / TF / PY / JS / TS / JAVA / GO | yes | text | text span | heading/comment | heading/comment | line | no |
| DOCX | yes | OOXML ZIP | paragraph / table / header / footer | yes | yes | section, table | no |
| XLSX | yes | OOXML ZIP | cell + hidden sheet | yes | yes | sheet, row, column | no |
| PPTX | yes | OOXML ZIP | shape | yes | yes | slide | no |
| PDF (native text) | yes | content stream | page text + bbox | **no** | **no** | page | no |
| PDF (scanned image) | yes | PDF + raster | embedded image + layout bbox | **no** | **no** | page | no |
| PNG / JPG / JPEG | yes | header + pixels | layout bbox | **no** | **no** | bbox | no |

## Language routing

| Renderer family | `th` | `en` | `mixed` | Behaviour when Thai is requested |
|---|---|---|---|---|
| Text, CSV, JSON, YAML, XML, config, code | yes | yes | yes | localized labels/comments; machine keys stay English |
| DOCX / XLSX / PPTX | yes | yes | yes | full Thai labels and bilingual mixed headers |
| PDF | no | yes | no | `language_routing: pdf_latin_only`, content rendered in English |
| PNG / JPG / JPEG | no | yes | no | `language_routing: <ext>_latin_only`, content rendered in English |
| LOG | no | yes | no | `language_routing: log_english_only`, technical English log |

The PDF, image and log renderers **raise** on non-Latin text instead of replacing
it with `?`. A requested Thai PDF/image is therefore routed to English and the
routing is recorded per attachment; a Thai DOCX in the same case keeps Thai
content. It is never silently mangled.

## Ground-truth location kinds

`prompt_span`, `text_span`, `csv_cell`, `json_path`, `yaml_path`, `xml_path`,
`key_path`, `xlsx_cell`, `docx_paragraph`, `docx_table_cell`, `docx_header`,
`docx_footer`, `pptx_shape`, `pdf_text`, `pdf_image`, `image_ocr`.

## Verification boundary

- Every non-image attachment is reopened with a parser and every recorded
  location is resolved before the case is accepted.
- Images and scanned PDFs are `verified_layout` / `verified_partial`: the
  expected text and bounding box come from the pre-render document, not from an
  OCR engine. Image entities are atomic: a value is never split across lines
  (`entity_strategy: atomic_line`, `fragment_count: 1`), the canvas widens
  instead, and the verifier rejects a fragment annotation.
- Log lines are parsed back after rendering and their timestamps must be
  non-decreasing; a single line or an unparseable line is never accepted as
  ordered.
- No OCR accuracy, detector accuracy, gateway benchmark or latency claim is
  made.
- Optional dependencies: none. The runtime is standard library only.

## Cross-file and structure features

| Capability | Implemented | Verified by |
|---|---|---|
| Shared scenario IDs (incident, request, invoice, ticket, transaction) | yes | `tests/test_v2_consistency.py` |
| Shared hosts, database endpoints, internal URLs | yes | `tests/test_v2_consistency.py`, `cross_file_links` |
| Shared people/customers across files | yes | `cross_file_links` |
| Invoice arithmetic, due-date and linked transaction amount/currency/reference | yes | `consistency_checks` (structured status) |
| Payroll gross - tax = net check | yes | `consistency_checks` |
| Statement running balance | yes | `consistency_checks` |
| Log timestamp ordering (parsed from rendered lines) | yes | `consistency_checks` |
| Structure references resolve and are user-visible | yes | `structure_references` + validation |
| Multi-file relationship evidence | yes | `bundle.relationship` + validation |
| Same-archetype and old/new bundles with before/after values | yes | `bundle` metadata + tests |
| Mixed-script content check | yes | `attachment.language_check` + measured gate |
| Measured language shares (thai/latin/neutral) | yes | `language_stats` + gate |
