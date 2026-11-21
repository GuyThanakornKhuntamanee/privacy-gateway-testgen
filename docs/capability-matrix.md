# Capability matrix (schema 2.1, v2.2 rendering)

This matrix describes what the repository actually renders and verifies in this
checkout. A "yes" means a unit test or a measured dataset report exercises it;
it is not a claim about a downstream gateway.

## File formats

| Format | Generate | Reopen | Verify | Thai | Mixed | Structure-aware | Dependency |
|---|---|---|---|---|---|---|---|
| TXT / MD | yes | yes | text span | yes | yes | line, section | stdlib |
| LOG | yes | yes | text span | **no** (technical English) | **no** | line | stdlib |
| CSV | yes | `csv` | cell | yes | yes | row, column | stdlib |
| JSON | yes | `json` | JSON path | note + entities | note + entities | key | stdlib |
| YAML / YML | yes | strict subset | YAML path | note + entities | note + entities | key | stdlib |
| XML | yes | ElementTree | XML path | note + entities | note + entities | key | stdlib |
| ENV / INI / CONF / TOML | yes | strict subset | key path | comments | comments | key | stdlib |
| SQL / TF / PY / JS / TS / JAVA / GO | yes | text | text span | heading/comment | heading/comment | line | stdlib |
| DOCX | yes | OOXML ZIP | paragraph / table / header / footer | yes | yes | section, table | stdlib |
| XLSX | yes | OOXML ZIP | cell + hidden sheet | yes | yes | sheet, row, column | stdlib |
| PPTX | yes | OOXML ZIP | shape | yes | yes | slide | stdlib |
| PDF (native text) | yes | pypdf text extraction | page text + bbox | yes | yes | page | reportlab, pypdf |
| PDF (hybrid) | yes | pypdf + PDF image objects | native text bbox + embedded-image bbox | yes | yes | page | reportlab, pypdf, Pillow |
| PDF (scanned page) | yes | PDF + raster | embedded image + layout bbox | yes | yes | page | reportlab, pypdf, Pillow |
| PNG / JPG / JPEG | yes | Pillow decode | layout bbox | yes | yes | bbox | Pillow |

## Language routing

| Renderer family | `th` | `en` | `mixed` | Behaviour when Thai is requested |
|---|---|---|---|---|
| Text, CSV, JSON, YAML, XML, config, code | yes | yes | yes | localized labels/comments; machine keys stay English |
| DOCX / XLSX / PPTX | yes | yes | yes | full Thai labels and bilingual mixed headers |
| PDF (native / hybrid / scanned) | yes | yes | yes | Thai text embedded as real PDF text; scanned/hybrid image regions use the raster renderer |
| PNG / JPG / JPEG | yes | yes | yes | Sarabun + FreeType + libraqm shaping |
| LOG | no | yes | no | `language_routing: log_english_only`, technical English log |

`language_capability` for `pdf`, `png`, `jpg` and `jpeg` is
`["th", "en", "mixed"]`. A renderer that cannot carry a language raises
(`RendererUnavailable` for a missing font or missing shaping support) instead of
writing `?`; the routing mechanism stays in place for any future renderer with a
narrower capability. A document whose measured script shares disagree with the
requested language is relabelled (`language_routing: relabelled_from_*`).

## Evaluation requirement

| Format | Evaluation requirement | Why |
|---|---|---|
| Native PDF, text, CSV, JSON, YAML, XML, config, code, DOCX, XLSX, PPTX | `direct_text_extraction` | the gateway can extract text without OCR |
| PNG / JPG / JPEG, scanned PDF, hybrid PDF image region | `ocr_required` | ground truth is layout-verified; the gateway under test performs the OCR |

`benchmark_safe_text_cases.jsonl` and `benchmark_safe_ocr_cases.jsonl` are
written separately, so an OCR benchmark never mixes in direct-text cases.

## Ground-truth location kinds

`prompt_span`, `text_span`, `csv_cell`, `json_path`, `yaml_path`, `xml_path`,
`key_path`, `xlsx_cell`, `docx_paragraph`, `docx_table_cell`, `docx_header`,
`docx_footer`, `pptx_shape`, `pdf_text`, `pdf_image`, `image_ocr`.

## Verification boundary

- Every non-image attachment is reopened with a parser and every recorded
  location is resolved before the case is accepted.
- Native PDFs are reopened with pypdf: each entity value and every canonical
  rendered line must come back after collapsing layout whitespace only, so a
  broken word (`exam ple.com`) still fails.
- Images and scanned/hybrid PDF image regions are `verified_layout` /
  `verified_partial`: the expected text and bounding box come from the
  pre-render document, not from an OCR engine. Image entities are atomic: a
  value is never split across lines (`entity_strategy: atomic_line`,
  `fragment_count: 1`), the canvas widens instead, and the verifier rejects a
  fragment annotation. Rotated rasters report `bbox_space: final`.
- Log lines are parsed back after rendering and their timestamps must be
  non-decreasing; a single line or an unparseable line is never accepted as
  ordered.
- No OCR accuracy, detector accuracy, gateway benchmark or latency claim is
  made.
- Synthetic disclosure is out-of-band: files carry no "synthetic" notice in the
  default `metadata` mode, so a detector cannot read a hint that suppresses a
  detection. `disclosure: banner` is available for artifacts shared with people.
- Runtime dependencies: `Pillow`, `reportlab`, `pypdf`. The font asset
  (Sarabun, SIL OFL 1.1) ships inside the package; no system font is discovered.

## Thai rendering matrix (v2.2)

| Format | Thai | English | Mixed | Text extraction | Layout ground truth | OCR needed |
|---|---:|---:|---:|---|---|---:|
| Native PDF | yes | yes | yes | yes (pypdf round-trip, per-entity) | page, block bbox | no |
| Hybrid PDF | yes | yes | yes | yes for native text; no for the image region | page bbox + image bbox | partly |
| Scanned PDF | yes | yes | yes | no | image bbox + page bbox | yes |
| PNG | yes | yes | yes | no | image bbox | yes |
| JPG / JPEG | yes | yes | yes | no | image bbox | yes |

"yes" is only written after the corresponding round-trip test in
`tests/test_v2_thai_rendering.py` and the `thai_file_render_rate`,
`native_pdf_text_extraction`, `raster_text_shaping` and `no_replacement_glyphs`
gates pass on a generated dataset.

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
