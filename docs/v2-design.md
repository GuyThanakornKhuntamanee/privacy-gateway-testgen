# v2 design: realistic request + attachment + ground truth

Status: implementation design for schema `2.1`. Schema `2.0` datasets remain
readable; new datasets use additive 2.1 fields. The v1 prompt-only generator and
its `1.0` schema are unchanged and remain the default.

## Problem

v1 produces realistic prompts but every test case is still text-only. Real
gateway traffic includes uploaded spreadsheets, PDFs, Office documents, images,
configuration files and logs. A text-only benchmark cannot measure file
ingestion, OCR, spreadsheet/table extraction, or cross-file policy decisions.

## Architecture

```
profile + seed
    -> scenario targets (persona, intent, prompt language, domains, attachments)
    -> case ScenarioPlan (shared people, hosts, IDs, timestamps, transactions)
    -> synthetic organisation (shared identities, systems)
    -> document archetype (meaning) + renderer (file format)
    -> per-attachment language + localization
    -> human-like prompt (incidental task, optional structure reference)
    -> span-first document composition
    -> real file bytes
    -> reopen + extract + verify
    -> cross-file links + consistency checks
    -> case, attachment metadata, file-aware ground truth
```

The v1 invariant is kept: entities are created before the document is composed
and inserted through a builder that records their location. Nothing is found by
searching a finished file. Unlike v1, the location is file-specific:
`json_path`, `csv_cell`, `xlsx_cell`, `docx_paragraph`, `pptx_shape`,
`pdf_text`, `image_ocr`, and so on.

### Separation of concerns

| Layer | Module | Responsibility |
|---|---|---|
| Content model | `v2/docmodel.py` | Blocks, cells, placements, document model |
| Organisation | `v2/org.py` | Coherent synthetic people, hosts, vendors, systems |
| Scenario | `v2/scenario.py` | Shared identities, IDs, timestamps and transactions |
| Localization | `v2/localization.py` | Thai/English/mixed labels, formatting and script checks |
| Realism | `v2/realism.py` | Personas, intents, prompt forms, imperfections, structure refs |
| Archetypes | `v2/archetypes.py` | Business meaning independent of file format |
| Renderers | `v2/renderers/` | Real TXT/CSV/JSON/YAML/XML/log/Office/PDF/image bytes |
| Verification | `v2/extract.py` | Reopen, parse, locate and re-check every annotation |
| Generation | `v2/generate.py` | Targets, bundles, dedupe, splits, export |
| Evaluation | `v2/evaluate.py` | Measured gates, language/consistency coverage |
| Interface | `v2/cli.py` | `generate-v2`, `validate-v2`, `report-v2`, `verify-v2` |

An archetype declares the business document (`payroll`, `incident_report`,
`kubernetes_manifest`) and which renderers can carry it. The same archetype can
therefore produce CSV, XLSX or PDF without duplicating content rules.

## Ground truth

Every entity occurrence records:

- `annotation_id` (unique occurrence), `canonical_entity_id` (same value across
  files), domain, type, exact value, detection/classification expectations;
- `source`: `prompt` or `attachment`;
- `source_attachment` (`ATT-001`) and `filename`;
- `location`: structured provenance for the renderer;
- `verification`: status, method and evidence.

Prompt entities also carry `character_start` / `character_end` under the v1
convention (`unicode_codepoints_0_based_end_exclusive`). File entities carry a
`location` object and, for text-like files, character offsets inside the file.

### Location kinds

| Kind | Fields |
|---|---|
| `text_span` | line, character_start, character_end |
| `csv_cell` | row, column, header |
| `json_path` | path (`$.employees[2].email`) |
| `yaml_path` | path, line |
| `xml_path` | path (`/invoice/customer/email`) |
| `key_path` | key, line, section |
| `xlsx_cell` | sheet, cell, row, column, header, hidden |
| `docx_paragraph` | paragraph, character_start, character_end |
| `docx_table_cell` | table, row, column |
| `docx_header` / `docx_footer` | character_start, character_end |
| `pptx_shape` | slide, shape, character_start, character_end |
| `pdf_text` | page, x, y, width, height, character_start, character_end |
| `pdf_image` | page, source_type, bbox, expected_ocr_text |
| `image_ocr` | width, height, bbox, expected_ocr_text, ocr_normalized |

`pdf_text` and `image_ocr` are not the same kind of evidence. A scanned PDF
records `source_type: embedded_image`; OCR output is an evaluation-stage
artifact and is never promoted to ground truth.

### Language model (2.1)

Each attachment selects its own language independently of the prompt. The
localization layer rewrites static text between placements, so entity values and
their offsets never change. Machine formats (`json`, `xml`, `yaml`, `env`,
`ini`, `conf`, `toml`, `sql`) keep English keys; titles, prose and comments can
be Thai, and JSON/XML/config documents receive a `_language_note`.

`mixed` is verified as **intra-document code-switching**: `attachment.language_check`
counts Thai and Latin characters and the evaluator requires both. A Thai name in
an English template is not enough.

PDF and image renderers are Latin-only. A Thai request is routed to English with
`language_routing` recorded; the renderer raises on non-Latin characters instead
of writing `?`. This is Option B in the brief: explicit unsupported, not
silently degraded.

### Scenario plan and cross-file links (2.1)

One `ScenarioPlan` per case owns shared people, organisation, hosts, database
endpoint, internal URL, private network, incident/ticket/invoice/request IDs,
timestamps, payment terms and transaction references. Builders request shared
values by key; the plan caches and returns the same `Entity`.

After rendering, every canonical entity that occurs in at least two attachments
becomes a `cross_file_link`; `bundle` records whether the case is a single file,
a related multi-file bundle, a same-archetype bundle or an old/new revision.
Old/new pairs use a deep copy of the first document plus one traceable change
(status, date or text field), never a full re-generation under the same name.

### Consistency and structure (2.1)

`consistency_checks` records invoice line arithmetic, VAT total, due date vs
payment terms, payroll gross/tax/net, statement running balance, ordered log
timestamps, cross-file identifier consistency and structure-reference
resolution. A failed check fails generation; `validate-v2` re-checks the
exported case.

`structure_references` are chosen only from structures the renderer reports
(sheets, rows, columns, pages, slides, headings, lines, keys). The prompt
contains a natural clause such as `ดู tab employee` or `หน้า 3`, and the
reference resolves against `attachment.structure`.

## Dataset layout

```
dataset/
  manifest.json
  cases.jsonl
  all.json
  stats.json
  train.jsonl validation.jsonl test.jsonl
  ground_truth/entities.jsonl
  attachments/TC-.../file.ext
```

The manifest includes the dataset ID, schema and generator versions, seed,
profile, fixed dataset epoch (no wall-clock timestamp, so output stays
byte-identical), distributions, verification summary, config/policy hashes and
per-file SHA-256.

## Safety

Only synthetic values are generated. Reserved example domains, RFC 1918 /
RFC 5737 / ULA networks, documented test card BINs, and `example`/`fake`
credential markers are reused from v1. Office files are macro-free ZIP/XML.
Spreadsheet formulas are limited to arithmetic over generated numbers. PDFs and
images contain no JavaScript, remote content or executables. Images are marked
`SYNTHETIC SAMPLE` and do not depict real people or real identity documents.

## Renderer dependencies

The package stays standard-library only:

- DOCX/XLSX/PPTX: `zipfile` + OOXML XML written directly;
- PDF: a small PDF 1.4 writer (Helvetica/WinAnsi, native text and image XObjects);
- PNG: `zlib` + CRC, with a bitmap font for OCR-oriented screenshots;
- JPEG: baseline grayscale encoder (no third-party imaging library);
- YAML/TOML/INI/ENV: purpose-built emitters for the generator's own subset.

No renderer invokes a shell, macro, network request or external binary.

## Determinism

All randomness comes from `random.Random(seed)`. ZIP timestamps are fixed at
1980-01-01, PDF/Office metadata uses a fixed epoch, JSON uses a stable key
order, and the manifest omits wall-clock time. The same config + seed produces
the same case JSON and attachment bytes.

## Migration from 1.0

- `schema_version` is `2.1`; v1 files are untouched and still validate with
  `validate`.
- v2 cases add `attachments`, file-aware `entities`, `persona`, `intent`,
  `profile`, `ambiguity`, `file_types` and verification evidence.
- v1 fields such as `prompt`, `language`, `domains`, `difficulty`, `polarity`,
  `action_expected` and `policy_scenario` keep their meaning.
- v2 is exposed through separate commands (`generate-v2`, `validate-v2`,
  `report-v2`); no existing CLI behaviour or v1 sample dataset changes.

## Migration from 2.0

- `schema_version` is `2.1`; 2.0 files still load and validate with
  `validate-v2`, and `report-v2` skips 2.1-only gates for them.
- Additive 2.1 fields: `prompt_language`, `content_languages`, `language_mode`,
  `language_coverage`, `scenario_id`, `cross_file_links`, `structure_references`,
  `document_profile`, `consistency_checks`, `bundle`; per attachment
  `language`, `language_mode`, `language_mix`, `language_capability`,
  `language_routing`, `language_check`, `structure`, `renderer_version`,
  `dependency_renderer` and `revision_changes`.
- Existing 2.0 fields keep their meaning. No field was renamed or removed.

## Acceptance criteria

1. v1 tests and the v1 evaluation gate still pass unchanged.
2. Every supported file family renders real bytes that reopen and parse.
3. Every annotation resolves at its recorded location or the case is marked
   `unverified`; rendering success alone is never accepted.
4. Same seed + config reproduces case JSON and attachment bytes.
5. Thai documents contain Thai labels; English documents stay English; mixed
   documents contain both scripts and are measured.
6. Prompt and attachment languages are independent and the matrix is reported.
7. Shared IDs, people, hosts, timestamps and transactions agree across files.
8. Invoice, payroll and statement arithmetic checks pass.
9. Structure references resolve to real sheets/pages/sections/rows/slides.
10. Same-archetype and old/new bundles record their relationship and changes.
11. No real personal data, working credential, live card number, private
    company host or macro exists in generated output.
12. The evaluation report contains only measured values and names limitations.

## Known limitations (2.1)

- The PDF renderer uses built-in WinAnsi fonts, so PDF attachment content is
  English/Latin; Thai PDF content is routed to DOCX/XLSX/TXT and marked with
  `language_routing`. The renderer raises on non-Latin text rather than
  substituting `?`.
- Images use a bundled bitmap font and are Latin-script only; Thai image
  scenarios are routed to English with explicit metadata.
- Image/scanned-PDF OCR is not performed with a third-party OCR engine in the
  test suite; image annotations are layout-verified and marked accordingly. At
  OCR difficulty 3–4 a rotation is applied after layout, so bounding boxes are
  in pre-render coordinates (`bbox_space: pre_render`).
- PPTX speaker notes and real PowerPoint tables are not emitted yet; slide body
  text and later-slide placement are supported.
- YAML/TOML/INI/ENV round-trip uses the generator's strict subset parser, not
  PyYAML/tomllib.
- Archives, audio, video, executables and password-protected containers are
  intentionally out of scope.
- Cross-file consistency is validated against generated annotations and the
  scenario plan, not by executing a downstream gateway.
