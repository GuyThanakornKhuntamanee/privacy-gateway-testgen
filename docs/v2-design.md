# v2 design: realistic request + attachment + ground truth

Status: implementation design for schema `2.0`. The v1 prompt-only generator and
its `1.0` schema are unchanged and remain the default.

## Problem

v1 produces realistic prompts but every test case is still text-only. Real
gateway traffic includes uploaded spreadsheets, PDFs, Office documents, images,
configuration files and logs. A text-only benchmark cannot measure file
ingestion, OCR, spreadsheet/table extraction, or cross-file policy decisions.

## Architecture

```
profile + seed
    -> scenario targets (persona, intent, language, domains, attachments)
    -> synthetic organisation (shared identities, hosts, systems)
    -> document archetype (meaning) + renderer (file format)
    -> human-like prompt (incidental task, not "detect the PII")
    -> span-first document composition
    -> real file bytes
    -> reopen + extract + verify
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
| Realism | `v2/realism.py` | Personas, intents, prompt forms, imperfections |
| Archetypes | `v2/archetypes.py` | Business meaning independent of file format |
| Renderers | `v2/renderers/` | Real TXT/CSV/JSON/YAML/XML/log/Office/PDF/image bytes |
| Verification | `v2/extract.py` | Reopen, parse, locate and re-check every annotation |
| Generation | `v2/generate.py` | Targets, multi-file bundles, dedupe, splits, export |
| Evaluation | `v2/evaluate.py` | Measured gates, coverage, realism diagnostics |
| Interface | `v2/cli.py` | `generate-v2`, `validate-v2`, `report-v2` |

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

- `schema_version` is `2.0`; v1 files are untouched and still validate with
  `validate`.
- v2 cases add `attachments`, file-aware `entities`, `persona`, `intent`,
  `profile`, `ambiguity`, `file_types` and verification evidence.
- v1 fields such as `prompt`, `language`, `domains`, `difficulty`, `polarity`,
  `action_expected` and `policy_scenario` keep their meaning.
- v2 is exposed through separate commands (`generate-v2`, `validate-v2`,
  `report-v2`); no existing CLI behaviour or v1 sample dataset changes.

## Acceptance criteria

1. v1 tests and the v1 evaluation gate still pass unchanged.
2. Every P0/P1/P2 file family renders real bytes that reopen and parse.
3. Every annotation either resolves at its recorded location or the case is
   marked `unverified`; no silent assumption that rendering succeeded.
4. Same seed + config reproduces case JSON and attachment bytes.
5. Single/multi-domain, negative, ambiguous, prompt-only, single-file,
   multi-file and OCR-oriented cases are present.
6. Prompt openings and sentence skeletons meet configured repetition limits.
7. No real personal data, working credential, live card number, private
   company host or macro exists in generated output.
8. The evaluation report contains only measured values and names limitations.

## Known limitations (v2.0)

- The PDF renderer uses built-in WinAnsi fonts, so PDF attachment content is
  English/Latin; Thai PDF content is routed to DOCX/XLSX/TXT instead. Thai text
  is fully supported in the XML-based Office formats and text formats.
- Images use a bundled bitmap font, so OCR images are Latin-script only.
  Thai OCR images are out of scope for this version.
- Image OCR is not performed with a third-party OCR engine in the test suite;
  image annotations are verified at render-layout level and marked accordingly.
  At OCR difficulty 3–4 a rotation is applied after layout, so image bounding
  boxes are recorded in pre-render coordinates (`bbox_space: pre_render`).
- PPTX speaker notes and real PowerPoint tables are not emitted yet; slide body
  text and later-slide placement are supported.
- YAML/TOML/INI/ENV round-trip uses the generator's strict subset parser, not
  PyYAML/tomllib.
- Archives, audio, video, executables and password-protected containers are
  intentionally out of scope.
