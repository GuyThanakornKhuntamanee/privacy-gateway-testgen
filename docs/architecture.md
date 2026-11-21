# Architecture

## Goal

Produce reproducible synthetic prompts with exact, machine-checkable ground
truth for privacy-gateway evaluation, across four domains and a wide range of
prompt shapes. The artifact is a dataset plus the tooling that proves it is
internally consistent.

Non-goals: implementing a gateway, detecting PII, claiming legal compliance,
or generating production credentials.

## Components

```
configuration (JSON)                 policy (JSON)
   seed, distributions, gates           actions, scenarios, rules
            |                                   |
            v                                   v
   +---------------------------------------------------+
   |                 DatasetGenerator                  |
   |  split assignment -> target sampling -> templates |
   +----------------------+----------------------------+
                          |
             +------------+-------------+
             |                          |
      entity factories            prompt templates
      (pii/payment/secrets/       (short/medium/long,
       infra/lookalike)            contextual, negative)
             |                          |
             +------------+-------------+
                          |
                 PromptBuilder (records spans)
                          |
                    Draft case assembly
                          |
              policy resolution (strictest action)
                          |
                 validation (schema + spans + policy)
                          |
             +------------+-------------+
             |                          |
      JSONL/JSON export          quality-gate evaluator
      + manifest hashes          + markdown report
```

## Data flow

1. **Configuration** is loaded from JSON and validated. Defaults for omitted
   distribution keys and gates are merged in.
2. **Split assignment** distributes template *families* across train,
   validation and test. The strata are negative templates and positive
   short/medium/long templates, so every split gets a representative mix.
   A family appears in exactly one split.
3. **Target sampling** draws language, length class, difficulty, polarity,
   multi-domain preference and entity density from configured weights.
4. **Candidate selection** prefers templates matching the requested length and
   difficulty, then multi-domain templates within that set. Usage balancing
   (`1 / (1 + usage)`) prevents a split from collapsing onto one family.
5. **Template execution** draws entities from a per-case `EntityPool` and
   appends them through `PromptBuilder`. The builder stores start/end offsets
   at insertion time. For long prompts, harmless padding is inserted *before*
   the final request so the prompt still ends with a task.
6. **Case assembly** derives domains, entity types, styles, taxonomy and
   policy expectations. Policy resolution evaluates every matching rule and
   keeps the strictest action; scenario floors apply only when entities were
   detected.
7. **Validation** re-slices the finished prompt at every recorded span,
   checks taxonomy and policy fields, and verifies IDs/prompts are unique.
8. **Deduplication** rejects normalized exact duplicates and near-duplicates
   (character 8-shingle Jaccard ≥ configured threshold) across the whole
   dataset, including across splits.
9. **Export** writes deterministic JSONL/JSON plus a manifest with config and
   policy hashes and per-file SHA-256s. No timestamps are written.
10. **Evaluation** re-runs generation and compares canonical JSON to prove
    reproducibility, then computes coverage and gate results.

## Key design decisions

### Span-first, not post-hoc annotation

The most common failure in synthetic privacy datasets is drift between the
prompt text and its labels. Generating the value first and recording the span
at append time makes the invariant structural rather than probabilistic.
`validation.py` re-checks the invariant anyway, so a future template mistake
fails loudly instead of producing plausible-looking wrong data.

### Deterministic entity factories

Every factory is a pure function of the seeded RNG (and the per-case fictional
organisation/language). Values are realistic in shape but non-functional:
reserved example domains, RFC 1918/5737 networks, test card BINs, explicit
`example`/`fake` markers, and PEM labels that parsers reject. This gives
detectors realistic patterns without creating publishable live secrets.

### Templates declare their own truth

A template declares `domains`, `length_class`, `difficulty`, `negative`,
`contextual`, `adversarial`, `structure` and `detection_mode`. The test suite
builds every template in all three languages and asserts that declared domains
equal the actual expected domains and that measured prompt length falls in the
declared class. This keeps the generator's sampling honest.

### Family-disjoint splits

Randomly splitting cases leaks near-identical templates into the test set. This
project assigns whole template families to one split and additionally checks
exact prompts and 8-shingle near-duplicates across splits. The trade-off is
that validation/test have fewer distinct families on a small dataset; adding
templates is the intended remedy.

### Policy as configuration, with explicit precedence

Actions are ordered from least to most strict. A rule per domain/entity type
contributes an action; the strictest wins. Scenarios add a floor for detected
entities and determine routing. This makes "highest applicable action
prevails" testable and lets a deployment replace the illustrative default with
its own policy without changing code.

### Declared, justified dependencies

The package depends on `Pillow` (raster rendering + Thai shaping), `reportlab`
(native PDF font embedding) and `pypdf` (independent PDF text extraction), and
makes no network calls. Everything else is stdlib and tests use `unittest`.
Each dependency exists because the alternative was a fragile reimplementation of
FreeType/HarfBuzz or of a Type0 PDF font writer; the rationale is recorded in
`docs/v2.2-thai-rendering-design.md`. JSON is the configuration language; YAML is
not required.

### Separate verification for imported prompts

The generator's spans are verified by construction. Imported or LLM-authored
prompts do not get that guarantee. `annotations.py` verifies offsets, can
repair a unique occurrence, refuses to guess when a value is ambiguous, and
reports semantic verification separately. This avoids silently treating
generated labels as authoritative ground truth.

## v2 file-aware architecture

Schema `2.1` is additive. v1 prompts, exports and gates remain unchanged; v2
adds a new package at `src/privacy_gateway_testgen/v2/`.

```
profile + seed
  -> target sampling (persona, intent, prompt language, domains, attachments)
  -> ScenarioPlan (shared people, hosts, database endpoints, IDs, transactions)
  -> per-attachment language (th/en/mixed) and per-attachment English-only routing
  -> document archetype (business meaning)
  -> renderer (txt/csv/json/yaml/xml/log/md/env/ini/conf/toml/sql/tf/code
               docx/xlsx/pptx/pdf/png/jpg)
  -> span-first document composition + localization
  -> real file bytes
  -> reopen, parse, locate and verify
  -> cross-file links + structured consistency checks
  -> case + attachment metadata + file-aware ground truth
  -> benchmark-safe subset + benchmark_ready in the report
```

The same rule as v1 applies: entities are created first and inserted through a
builder that records their position. A renderer maps that logical position to
file-specific provenance rather than searching the finished file.

| Module | Responsibility |
|---|---|
| `v2/docmodel.py` | blocks, cells, placements, document/slide model |
| `v2/org.py` | one coherent fictional organisation per case |
| `v2/scenario.py` | one scenario plan: shared identities, IDs, hosts, timestamps |
| `v2/localization.py` | Thai/English/mixed labels, Thai formatting, script checks |
| `v2/realism.py` | personas, intents, natural prompt forms, structure references |
| `v2/archetypes.py` | 69 business archetypes across HR, finance, sales, healthcare, IT, management and operations |
| `v2/renderers/textfmt.py` | text, CSV, JSON, YAML, XML, logs, configs, SQL, Terraform, code |
| `v2/renderers/ooxml.py` | macro-free DOCX/XLSX/PPTX via `zipfile` + OOXML XML |
| `v2/renderers/pdf.py` | native Thai/English PDF (embedded Sarabun + ToUnicode), scanned and hybrid pages via ReportLab |
| `v2/renderers/images.py` | PNG/JPEG screenshots and scans with Pillow + FreeType + libraqm shaping and degradation |
| `v2/renderers/textlayout.py` | cluster-safe, entity-atomic line breaking and extraction normalization |
| `v2/renderers/fonts.py` | package-relative bundled font resolution and shaping capability check |
| `v2/extract.py` | reopen/parse/locate verification |
| `v2/generate.py` | target sampling, bundles, dedupe, splits and export |
| `v2/evaluate.py` | measured coverage, language/consistency checks and realism diagnostics |
| `v2/verify.py` | re-verify an exported dataset from disk |

### Language boundary

Localization rewrites only static text between placements; entity values and
their offsets are untouched. Language labels are measured from Thai/Latin shares
over authored text (numeric characters are neutral), so a Thai name in an English
template does not make the file Thai. PDF and raster renderers declare
`th`/`en`/`mixed` capability and embed the bundled Sarabun font, so Thai content
stays Thai in the file; `log` remains English-only and records
`language_routing: log_english_only`. A document whose measured shares disagree
with the request is relabelled (`relabelled_from_*`) per attachment, never
case-wide.

### Scenario and consistency boundary

`ScenarioPlan.shared()` caches a value per role, so the database endpoint in
`prod.env`, the incident report and the deployment log are the same `Entity`.
Financial facts (line items, subtotal, VAT, total, currency, transaction
reference, payment schedule) are plan-level, so an invoice and its transaction
export agree by construction. After rendering, `generate.py` derives
`cross_file_links` from canonical identities and records structured
`consistency_checks` (`passed` / `failed` / `not_applicable` /
`not_evaluated`, with `evaluated_items`). Log timestamps are parsed from the
rendered lines, not asserted. `validate-v2` re-checks all of it, plus
structure-reference resolution and bundle relationship evidence, on the exported
dataset.

### v2 trust boundary

A renderer returning bytes is not proof that a case is correct. Every attachment
is reopened with the same class of parser an evaluation harness would use:

- text formats are decoded and the recorded character span is re-sliced;
- CSV is parsed with `csv`;
- JSON is parsed with `json` and the JSON path is resolved;
- XML is parsed with ElementTree and the element path is resolved;
- DOCX/XLSX/PPTX are opened as ZIP packages and the paragraph/cell/shape/slide
  locations are resolved;
- PDF content streams are parsed and the page/text location is checked;
- PNG/JPEG headers and dimensions are checked and image bounding boxes are
  bounds-checked.

Image OCR is **not** performed by the test suite. Image and scanned-PDF cases
are marked `verified_layout` / `verified_partial`; the expected OCR line is
pre-render ground truth, not an OCR result. An entity is never split across image
lines: the layout moves it or widens the canvas, and the verifier rejects a
fragment annotation.

### Determinism and safety in v2

- ZIP members use a fixed 1980-01-01 timestamp; Office/PDF metadata uses
  `2026-01-01T00:00:00Z`; no wall-clock time enters the manifest.
- Office packages are macro-free and contain no executables or external
  relationships except safe `example` hyperlinks.
- PDFs contain no JavaScript, launch actions, embedded files or remote content.
- Spreadsheets contain values, not formulas; no external links.
- Images are synthetic screenshots and clearly marked; no real identity
  documents or biometric data are generated.
- `v2/evaluate.py` reports measured gates, not aspirational claims.

## What v2 does not do

Archives (including recursive extraction), password-protected archives, audio,
video, speech recognition, executables and multimedia classification remain out
of scope. The renderer registry and `Doc` model are the extension points for a
future version.

## Extension points

- New entity value: add a factory and register it in `entities/*.py`.
- New prompt shape: add a builder and a `Template` entry in `templates.py`.
- New policy: add JSON scenarios/rules; no code change.
- New gate: add a metric and gate entry in `evaluation.py` and a threshold in
  the config.
- New export format: add a writer in `generator.py` and include it in the
  manifest.

## Failure modes and responses

| Failure | Response |
|---|---|
| Generated case fails validation | Raise immediately with the test ID and issues; never export |
| Cannot reach requested count | Fail with a clear message; do not silently shrink the dataset |
| Family has no candidates for a target | Relax difficulty then length within the same polarity; still produce a valid case |
| Near-duplicate exhaustion | Fail; add templates or lower the count |
| Policy rule references unknown action | Config validation fails before generation |
| Imported annotation has ambiguous value | Leave unresolved and exit non-zero; do not guess |

## Security boundaries

- The generator reads local JSON config and writes local files. It does not
  dereference URLs or call external services.
- Entity values are untrusted output only in the sense that they are synthetic;
  they are not executed.
- Prompt text may contain code fences, SQL, YAML and logs. They are inert
  strings and are never executed by the tool.
- The sample dataset is safe to publish, but downstream scanners may still flag
  realistic test patterns. Label it clearly and keep real policy files private
  when needed.
