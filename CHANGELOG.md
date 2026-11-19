# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
semantic versioning.

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
