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
counts Thai, Latin and neutral characters and reports shares over authored text
(entity values are measured separately and excluded from the classification, so
a Thai name in an English template does not make the file Thai). Labels come from
measurement, not from the request: `th` requires a Thai share of at least 0.30,
`en` a Latin share of at least 0.80, and `mixed` both at least 0.10 (all
configurable in `language_thresholds`). A file that does not satisfy its
requested language is relabelled (`language_routing: relabelled_from_*`) or
rejected; it is never silently accepted.

PDF and raster renderers carry Thai, English and mixed content (v2.2): native PDF
text is embedded Sarabun TrueType with a ToUnicode map, and raster text is shaped
with Pillow + libraqm. Only `log` is English-only, and the routing mechanism stays
per attachment. Rendering a Thai identity in its Thai form
(`ลลิตา พูลสวัสดิ์`) or its Latin form (`Lalita Poolsawat`) keeps one canonical
value, so both representations link to the same identity. A renderer that cannot
carry a language raises instead of writing `?`.

### Scenario plan and cross-file links (2.1)

One `ScenarioPlan` per case owns shared people, organisation, hosts, database
endpoint, internal URL, private network, incident/ticket/invoice/request IDs,
timestamps, payment terms, transaction references and the financial facts of the
case (line items, subtotal, VAT, total, currency, invoice/due/payment dates and
payment schedule). Builders request shared values by key; the plan caches and
returns the same `Entity`. A quotation/invoice and its transaction export read
`subtotal`, `tax`, `total`, `transaction_id` and `currency` from the same plan,
so one settled invoice means invoice total == transaction amount. An installment
plan would be recorded explicitly in `payment_schedule` instead of producing
accidental mismatches.

After rendering, every canonical entity that occurs in at least two attachments
becomes a `cross_file_link` with its canonical value and representation
variants; `bundle` records whether the case is a single file, a related
multi-file bundle, a same-archetype bundle or an old/new revision. A multi-file
bundle must carry relationship evidence (a shared canonical entity, a controlled
revision or the same archetype); otherwise it is marked
`intentionally_unrelated` and must be an explicit negative/ambiguous case.
Old/new pairs use a deep copy of the first document plus one meaningful change:
status, due date, amount, phone, timeline time or endpoint, recorded with
before/after values and a location in both documents. Cosmetic "(revised)"
suffixes and note-only revisions are not produced.

Log timestamps come from the scenario timeline in one format per log (ISO,
bracket or JSON), including the final ERROR line. The rendered lines are parsed
back and compared chronologically; a single line is `not_evaluated`, never
`passed`.

### Consistency and structure (2.1)

`consistency_checks` records invoice line arithmetic, VAT total, due date vs
payment terms, payroll gross/tax/net, statement running balance, parsed log
timestamp order, linked amount/currency/transaction-reference agreement,
cross-file identifier consistency and structure-reference resolution. Every
check has `check`, `status` (`passed`, `failed`, `not_applicable`,
`not_evaluated`), `evaluated_items` and `details`; the legacy `passed` boolean is
kept as `status == "passed"`. A check with nothing to evaluate is
`not_applicable`, not a pass: `all([])` is not evidence. `validate-v2` rejects a
failed check and a status/boolean contradiction.

`structure_references` are chosen only from structures a reader can see
(sheets/rows/columns for XLSX, rows/columns for CSV, pages/sections for PDF,
slides for PPTX, sections/lines for text and logs, keys for structured config).
Images are deliberately excluded: a flattened screenshot has no user-visible row
or column to cite. The prompt contains a natural clause such as `ดู tab
employee` or `หน้า 3`, and the reference resolves against
`attachment.structure`.

## Dataset layout

```
dataset/
  manifest.json
  cases.jsonl
  all.json
  stats.json
  benchmark_safe_cases.jsonl
  benchmark_excluded_cases.jsonl
  train.jsonl validation.jsonl test.jsonl
  ground_truth/entities.jsonl
  attachments/TC-.../file.ext
```

The manifest includes the dataset ID, schema and generator versions, seed,
profile, fixed dataset epoch (no wall-clock timestamp, so output stays
byte-identical), distributions, structured consistency status, verification
summary, config/policy hashes and per-file SHA-256. `benchmark_safe_cases.jsonl`
contains only cases whose ground truth is fully verified, whose language and
consistency evidence is valid and which are not `verified_partial`;
`benchmark_excluded_cases.jsonl` lists every excluded case with its reasons.

## Benchmark readiness

`report-v2` computes `benchmark_ready` from the dataset and its verification
output, not from the unit tests. It requires: no failed ground-truth
verification, no failed or unevaluated consistency check, no known high
correctness issue, a valid log timeline and atomic image entities, valid
measured language metadata, passing safety checks, no unresolved schema error
and a measured reproducibility check (`--check-reproducible`). Reasons are
listed when it is false. Reports themselves are deterministic:
`evaluation.json` and `evaluation.md` contain no timestamp or absolute path and
are byte-identical across `PYTHONHASHSEED` values; `verification.json` contains
the dataset path, so it is identical for the same location.

## Safety

Only synthetic values are generated. Reserved example domains, RFC 1918 /
RFC 5737 / ULA networks, documented test card BINs, and `example`/`fake`
credential markers are reused from v1. Office files are macro-free ZIP/XML.
No spreadsheet formulas are emitted (cells hold values; sheets can be hidden).
PDFs and images contain no JavaScript, remote content or executables. Images are
marked `SYNTHETIC SAMPLE` and do not depict real people or real identity
documents. Synthetic phone numbers, national-ID-shaped values and bank accounts
are realistic by design; their collision risk is documented in `SECURITY.md`.

## Renderer dependencies

Declared dependencies, introduced in v2.2 for Thai PDF/image rendering:

- `Pillow` (FreeType glyphs, libraqm shaping, PNG/JPEG encoders, degradation);
- `reportlab` (PDF canvas, TrueType embedding, ToUnicode maps);
- `pypdf` (independent PDF text extraction during verification).

Bundled asset: Sarabun Regular/Bold (SIL OFL 1.1) inside the package. No system
font is discovered and no renderer falls back to another face.

Everything else stays stdlib:

- DOCX/XLSX/PPTX: `zipfile` + OOXML XML written directly;
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
  `validate-v2`, and `report-v2` skips 2.1-only gates for them. The immutable
  fixture `datasets/compat/v2.0-sample/` is validated in the test suite and in
  CI; sample generation never writes into it.
- Additive 2.1 fields: `prompt_language`, `content_languages`, `language_mode`,
  `language_coverage`, `language_stats`, `scenario_id`, `cross_file_links`,
  `structure_references`, `document_profile`, `consistency_checks`, `bundle`;
  per attachment `language`, `language_mode`, `language_mix`,
  `language_capability`, `language_routing`, `language_check`, `structure`,
  `renderer_version`, `dependency_renderer` and `revision_changes`; per entity
  `canonical_entity_value`.
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

## Known limitations (2.2)

- Native PDF text is embedded Sarabun TrueType with a ToUnicode map, so Thai and
  mixed text extract back exactly. Byte-identical PDF bytes hold for one pinned
  ReportLab version on one platform; across versions only content (text, spans,
  boxes, case JSON) is reproducible.
- Image/scanned-PDF OCR is not performed with a third-party OCR engine in the
  test suite; image annotations are layout-verified and marked accordingly.
  Rotation at OCR difficulty 3-4 is applied after layout and the bounding boxes
  are transformed with it (`bbox_space: final`).
- Raster cases are trustworthy testcases but require OCR from the gateway under
  test; they are listed in the separate OCR-required benchmark subset.
- PPTX speaker notes and real PowerPoint tables are not emitted yet; slide body
  text and later-slide placement are supported.
- YAML/TOML/INI/ENV round-trip uses the generator's strict subset parser, not
  PyYAML/tomllib.
- Archives, audio, video, executables and password-protected containers are
  intentionally out of scope.
- Cross-file consistency is validated against generated annotations and the
  scenario plan, not by executing a downstream gateway.
