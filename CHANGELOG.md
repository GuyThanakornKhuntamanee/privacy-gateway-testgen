# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
semantic versioning.

## [0.4.0] - 2026-11-21

### Added

- Native Thai PDF text: the PDF renderer embeds the bundled Sarabun TrueType
  font (regular + bold) with a ToUnicode map, so Thai, English and mixed content
  are real PDF text and extract back exactly. Scanned pages and hybrid pages
  (native prose plus an embedded screenshot region) are supported, and their
  annotations record `source_type` (`native_text`, `scanned_page`,
  `embedded_image`).
- Thai raster rendering: `png`, `jpg` and `jpeg` are drawn with Pillow/FreeType
  and libraqm shaping, including combining-mark placement, Thai digits and `฿`.
  Degradation (noise, blur, small rotation, brightness gradient) is seeded from
  the case, and rotation is applied to the recorded boxes (`bbox_space: final`).
- `v2/renderers/textlayout.py`: cluster-safe, entity-atomic line breaking shared
  by the PDF and raster renderers, plus structure-aware extraction
  normalization.
- `v2/renderers/fonts.py` and `src/privacy_gateway_testgen/assets/fonts/`:
  package-relative Sarabun asset, OFL license text and a shaping capability
  check that raises rather than silently falling back.
- Attachment metadata: `evaluation_requirement`
  (`direct_text_extraction` / `ocr_required`), `render_mode` and `text_shaping`.
- Benchmark subsets are split by modality: `benchmark_safe_text_cases.jsonl` and
  `benchmark_safe_ocr_cases.jsonl` (raster cases are no longer excluded for
  needing OCR from the gateway under test).
- `thai-rendering` profile and `datasets/v2-thai-sample` (16 cases / 24 files:
  Thai native, scanned and hybrid PDFs, Thai PNG/JPG/JPEG screenshots, mixed
  script images, cross-file Thai cases).
- Four measured gates: `thai_file_render_rate`, `raster_text_shaping`,
  `native_pdf_text_extraction` and `no_replacement_glyphs`.
- `tests/test_v2_thai_rendering.py` (29 round-trip, determinism and cross-file
  tests).

### Changed

- Runtime dependencies are declared and pinned: `Pillow`, `reportlab`, `pypdf`
  (package version 0.4.0, dataset version 2.2.0).
- Synthetic disclosure is out-of-band by default (`disclosure: metadata`):
  generated prompts and files carry no "synthetic"/"fictional" notice, so a
  detector under test cannot read a hint that suppresses a detection. The marking
  moved to `attachments[].synthetic`, `manifest.json` (`synthetic`, `disclosure`,
  `synthetic_notice`) and a new `NOTICE.md` in every dataset directory.
  `disclosure: banner` restores the previous visible notices.
- `verification.json` records the dataset folder name instead of an absolute
  path, so committed reports carry no machine-specific path; the project URLs in
  `pyproject.toml` point at the real repository.
- CI regenerates the committed v2 samples and reports and fails on drift, and the
  gate runs on `feat/**`/`fix/**` pushes as well as `main`.
- PDF text verification uses pypdf instead of a regex over the content stream,
  and compares collapsed-whitespace text so `exam ple.com` still fails against
  `example.com`.

### Fixed

- Old/new bundles can no longer contain two byte-identical files: a revision is
  applied only to the structure the target renderer emits, record-only formats
  fall back to a related render, and a rendered file that duplicates another one
  is rejected.
- Relabelling a document to `en` rebuilds it in English instead of leaving Thai
  headings behind; slide titles now count toward the language measurement, so an
  English deck really is English.
- Prompts no longer ask to compare "these two" when the case carries fewer than
  two attachments.
- Re-localizing a document no longer stacks translations in front of a label
  (`อ้างอิง / อ้างอิง / อ้างอิง:`); bilingual `ไทย / English:` labels are collapsed
  or kept as one pair.
- Raster layout could drop the last lines of a long document because the canvas
  height ignored the header block; chrome metrics now drive both size and
  drawing.

### Removed

- Automatic Latin-only routing for `pdf`, `png`, `jpg` and `jpeg`. `log` remains
  English-only and the routing mechanism is kept for renderers with a narrower
  capability.

## [0.3.1] - 2026-11-20

### Fixed

- Log timestamps are generated from the scenario timeline and the rendered lines
  are parsed back; an out-of-order log (including the final ERROR line) now fails
  validation instead of being reported as ordered. Bracket-format logs keep the
  full time of day.
- Invoices/quotations and their transaction export read one total, currency,
  transaction reference and payment schedule from the `ScenarioPlan`; linked
  amount/currency/reference checks are real and a mismatch fails.
- Image ground truth keeps entities atomic on one line and widens the canvas
  instead of splitting a value; the image verifier rejects a fragment annotation.
- Language labels are measured from Thai/Latin shares over authored text, not
  from script presence; documents that miss their requested thresholds are
  relabelled or rejected, and `language_stats` is reported.
- `Contact N` and `contactN@example.com` placeholders are gone: documents use a
  realistic synthetic organisation identity that is not an annotated target.
- Reports are deterministic across `PYTHONHASHSEED` values (sorted n-grams,
  deterministic tie-breaking, no timestamps in `evaluation.json`/`evaluation.md`).
- Static labels inside compound lines (`Subtotal: ... VAT 7%: ... Total: ...`)
  are localized; residual English labels in Thai documents are reported and
  gated at zero.
- Latin-only rendering is per attachment: a Thai DOCX next to an English PDF
  keeps Thai content, and both representations share one canonical identity.
- Thai addresses now come from a curated tambon/amphoe/province/postcode table.
- Thai imperfection no longer mutates Thai graphemes; it uses particles, spacing
  and punctuation only.
- Prompt composition uses particle-free intent cores, context/persona
  compatibility and a duplicate-phrase check instead of blind concatenation.
- Prompt-only cases use seven content forms (email, chat, ticket, notes, table,
  log fragment, code/config, short no-paste) instead of one fenced paste.
- Structure references only cite structures a reader can see; images never get
  row/column references.
- Multi-file bundles must carry relationship evidence; unrelated bundles are
  explicit negative/ambiguous cases.
- Old/new revisions change a real value (status, date, amount, phone, time or
  endpoint) with before/after values and locations in both documents.
- Consistency checks carry `status` (`passed`, `failed`, `not_applicable`,
  `not_evaluated`) and `evaluated_items`; `not_applicable` is not a pass.

### Added

- `benchmark_ready` in `report-v2` with per-check evidence and listed reasons,
  plus `benchmark_safe_cases.jsonl` / `benchmark_excluded_cases.jsonl`.
- Immutable schema 2.0 fixture at `datasets/compat/v2.0-sample/`.
- CI runs v2 generation, validation, verification, reporting, reproducibility,
  hash-seed report comparison and the 2.0 fixture.
- 37 correctness regression tests; 167 tests total.
- Documented synthetic-identifier collision risk in `SECURITY.md`.

### Changed

- `datasets/v2-sample` is generated with the `benchmark-balanced` profile so it
  covers text, structured text, Office, spreadsheet, PDF, image, config and log.
- `dataset_version` is `2.1.1`; package version `0.3.1`.

## [0.3.0] - 2026-11-20

### Added

- Additive schema `2.1` with `prompt_language`, `content_languages`,
  `language_mode`, `language_coverage`, `scenario_id`, `cross_file_links`,
  `structure_references`, `document_profile`, `consistency_checks` and
  `bundle`.
- Central localization layer for Thai/English/mixed titles, headings, table
  headers, sheet names, status values, notes and Thai date/currency formatting.
- Per-attachment language metadata and generation; the prompt/attachment
  language matrix is measured in reports.
- Case-level `ScenarioPlan` for shared people, hosts, database endpoints, IDs,
  timestamps, payment terms and transaction references.
- Cross-file link derivation and validation, plus arithmetic checks for
  invoices, payroll and bank statements.
- Structure-aware prompts that cite real sheets, pages, sections, rows, slides,
  lines or keys; every reference is resolved by validation.
- Multi-file, same-archetype and old/new bundles with traceable revision
  changes.
- CSV delimiter variation, log format variation, optional report sections and
  localized spreadsheet sheet names.
- New tests: localization, mixed script, per-attachment language, routing,
  cross-file consistency, arithmetic, structure references and old/new bundles.
- `docs/capability-matrix.md`.

### Changed

- Schema version is `2.1`; `dataset_version` is `2.1.0`; package version `0.3.0`.
- PDF and image renderers now raise on non-Latin text instead of writing `?`;
  Thai requests are routed and recorded.
- Thai documents are localized at document level while entity placements stay
  exact.
- 2.0 datasets remain valid for `validate-v2`; 2.1-only report gates are skipped
  for 2.0.

### Known limitations

- PDF content is English/Latin only; Thai PDF routes to DOCX/XLSX/TXT.
- OCR images are Latin-script bitmap text; image/scanned-PDF annotations remain
  layout-verified, not OCR-verified.
- PPTX speaker notes and native tables are not emitted.
- YAML/TOML/INI/ENV parsing uses the generator's strict subset.
- Archives, password-protected files, audio, video and executables are out of
  scope.

## [0.2.0] - 2026-11-20

### Added

- Additive schema `2.0` file-aware generator (`generate-v2`, `validate-v2`,
  `report-v2`, `verify-v2`, `list-profiles-v2`, `list-archetypes-v2`).
- Real attachment generation: TXT, CSV, JSON, YAML/YML, XML, LOG, MD, ENV, INI,
  CONF, TOML, SQL, Terraform, Python/JS/TS/Java/Go, DOCX, XLSX, PPTX, PDF, PNG,
  JPG/JPEG. OOXML files are macro-free; images use a pure-Python rasterizer.
- File-aware ground truth locations: `csv_cell`, `json_path`, `yaml_path`,
  `xml_path`, `key_path`, `xlsx_cell`, `docx_paragraph`, `docx_table_cell`,
  `docx_header`/`docx_footer`, `pptx_shape`, `pdf_text`, `pdf_image`,
  `image_ocr` and `text_span`.
- 69 document archetypes across HR, finance, sales/CRM, healthcare, IT, management
  and operations; one archetype can render as multiple formats.
- Synthetic organisation profiles with coherent people, customers, vendors,
  hosts, endpoints and projects shared across a case.
- Human-like prompt engine with 16 personas, 22 intents, Thai/English/mixed
  templates, configurable formality, typos, fragments, code switching and
  destination context.
- Negative, ambiguous, multi-domain and multi-attachment cases with per-file
  provenance.
- Seven generation profiles: `benchmark-balanced`, `real-world-enterprise`,
  `thai-enterprise`, `developer-security`, `office-documents`, `ocr` and
  `negative-hard`, plus custom profile files.
- File round-trip verification, dataset re-verification from disk, duplicate and
  document-fingerprint checks, measured coverage/realism reports.
- `datasets/v2-sample` (72 cases, 70 files) and `reports/v2/`.
- 39 additional unittest cases (112 total) covering every file family.

### Changed

- Package version `0.2.0`; v1 schema `1.0`, commands and sample dataset are
  unchanged.

### Known limitations

- PDF content is Latin/English only because built-in PDF fonts are WinAnsi.
- OCR images are Latin-script bitmap text; image/scanned-PDF annotations are
  layout-verified, not OCR-verified.
- PPTX speaker notes and native tables are not emitted.
- YAML/TOML/INI/ENV parsing uses the generator's strict subset.
- Archives, password-protected files, audio, video and executables are out of
  scope.

## [0.1.0] - 2026-11-09

### Added

- Agent Skill (`SKILL.md`) and a standard-library Python package for generating
  synthetic privacy-gateway test prompts.
- Four entity domains: PII, payment data, secrets/credentials, and
  infrastructure, plus a lookalike domain for negative cases.
- Deterministic span-recording prompt builder; exact ground truth by
  construction.
- 31 prompt templates covering short, medium, long, contextual, mixed-domain,
  negative and adversarial styles across Thai, English and mixed language.
- Configurable seed, sample count, splits, domain/language/length/difficulty/
  entity-density distributions, negative and multi-domain ratios.
- Configurable policy actions, scenarios and per-entity rules with strictest-
  action precedence and routing expectations.
- JSONL/JSON export, statistics, manifest with SHA-256 hashes, versioning and
  template-family-disjoint splits with duplicate/near-duplicate rejection.
- Validation of schema, spans, taxonomy, policy expectations, national-ID
  checksums and card Luhn checks.
- Separate verification/repair stage for imported or LLM-authored annotations,
  with ambiguity refusal and semantic-verification reporting.
- Quality-gate evaluator with a generated JSON and Markdown report, including
  configured-vs-measured distribution deltas.
- Sample dataset, 73-test `unittest` suite, security scans, CI workflow,
  installation/usage/security/contribution/release documentation, and a
  skill-behavior evaluation summary.

### Known limitations

- Distribution weights are preferences; prompt length and difficulty are
  coupled to available template families.
- Validation/test splits are template-family-disjoint, so small datasets have
  fewer families per split.
- Only documented test card BINs are used; no PCI DSS compliance is claimed.
- The default policy is illustrative, not legal advice.
- LLM-authored prompts are not generated by this tool; imported annotations
  require human semantic review.
