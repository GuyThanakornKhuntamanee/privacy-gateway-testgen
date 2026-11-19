# privacy-gateway-testgen

Deterministic synthetic test prompts and **exact ground-truth** datasets for
privacy-aware data gateways, PII detection, DLP, privacy filters, masking /
tokenization / redaction, and AI sovereignty routing.

This is an Agent Skill plus a dependency-free Python package. It generates
short, medium and long prompts in Thai, English and mixed language across four
domains — PII, payment data, secrets/credentials, and infrastructure — with
multi-domain, contextual, adversarial and negative cases. Every sensitive value
is synthetic, every span is recorded during prompt construction, and every run
is reproducible from a seed.

> All examples are synthetic. Do not put real customer data, live credentials
> or production infrastructure into this tool.

## Why span-first generation

Most synthetic test generators write a prompt first and then ask a model (or a
regex) where the sensitive values are. Offsets drift, Thai text breaks, and the
"ground truth" quietly becomes a guess. This project inverts the order:

1. Generate a synthetic entity value.
2. Append it to the prompt through a builder that records its exact character
   span.
3. Validate that `prompt[start:end] == exact_entity_value` for every case.

The result is a dataset whose annotations are correct by construction. Imported
or LLM-authored prompts go through a separate `verify` stage and stay marked
`unverified` until a human checks the semantics.

## Quick start

Requires Python 3.9+. No third-party packages, no network, no paid API.

```bash
# from the repository root
PYTHONPATH=src python -m privacy_gateway_testgen generate \
  --config configs/default.json --out datasets/sample

PYTHONPATH=src python -m privacy_gateway_testgen validate \
  --input datasets/sample/all.jsonl --config configs/default.json

PYTHONPATH=src python -m privacy_gateway_testgen evaluate \
  --config configs/default.json --out reports --dataset-out datasets/sample
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m privacy_gateway_testgen generate --config configs/default.json --out datasets/sample
```

Optional editable install:

```bash
python -m pip install -e .
privacy-gateway-testgen generate --config configs/default.json --out datasets/sample
```

## v2: requests with real attachments

Schema `2.1` adds real files, per-attachment language, a case-level scenario
plan, cross-file consistency checks, structure-aware prompts and a realism
engine. The v1 command surface and sample dataset are unchanged. v2 has its own
commands:

```bash
PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 \
  --config configs/v2/default.json --profile real-world-enterprise \
  --out datasets/v2-sample

PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 \
  --dataset datasets/v2-sample --json

PYTHONPATH=src python -m privacy_gateway_testgen report-v2 \
  --dataset datasets/v2-sample --out reports/v2 --check-reproducible
```

`generate-v2` supports `--count`, `--seed`, `--profile`, `--file-types`,
`--domains`, `--files-only` and `--policy`. Profiles are
`benchmark-balanced`, `real-world-enterprise`, `thai-enterprise`,
`developer-security`, `office-documents`, `ocr` and `negative-hard`. A JSON file
path can also be passed to `--profile` for a custom profile.

### What a v2 case contains

A realistic prompt, zero to three attachments, per-entity provenance, policy
expectations, a shared scenario plan, consistency checks and verification
evidence:

```json
{
  "schema_version": "2.1",
  "test_id": "pgt2-trn-00002",
  "persona": "developer",
  "intent": "troubleshoot",
  "prompt": "นี้ config ล่าสุด ช่วยดูให้ทีว่าทำไม prod ต่อ db ไม่ได้",
  "prompt_language": "th",
  "scenario_id": "SCN-00002",
  "attachments": [{
    "attachment_id": "ATT-001",
    "filename": "prod.env",
    "extension": "env",
    "mime_type": "text/plain",
    "archetype": "application_environment_config",
    "expected_extraction_method": "direct_text",
    "language": "th",
    "language_mix": "Thai business prose with English technical terms",
    "language_capability": ["th", "en", "mixed"],
    "synthetic": true,
    "verification": {"status": "verified"}
  }],
  "domains": ["secrets", "infrastructure"],
  "entities": [{
    "annotation_id": "ENT-00001",
    "source": "attachment",
    "source_attachment": "ATT-001",
    "entity_type": "password",
    "exact_entity_value": "Example-Fake-Passw0rd-4821!",
    "detection_expected": true,
    "location": {"kind": "key_path", "key": "DB_PASSWORD", "line": 5}
  }],
  "cross_file_links": [],
  "structure_references": [],
  "consistency_checks": [{"check": "cross_file_identifiers", "passed": true}]
}
```

The actual v2 schema uses lower-case domain names (`secrets`,
`infrastructure`) and the exact field set in
[`schemas/testcase.v2.schema.json`](schemas/testcase.v2.schema.json).

### Supported files

Real, parseable files are emitted for: `txt`, `csv`, `json`, `yaml`, `yml`,
`xml`, `log`, `md`, `env`, `ini`, `conf`, `toml`, `sql`, `tf`, `py`, `js`, `ts`,
`java`, `go`, `docx`, `xlsx`, `pptx`, `pdf`, `png`, `jpg` and `jpeg`.

- DOCX/XLSX/PPTX are macro-free OOXML ZIP packages.
- PDF supports native text, multi-page tables and scanned image-only pages.
- Images are synthetic screenshots/scans with configurable OCR difficulty.
- Spreadsheets support multiple sheets, hidden sheets, Thai/English headers and
  empty/mixed-type cells.
- Ground truth uses `xlsx_cell`, `docx_paragraph`, `docx_table_cell`,
  `pptx_shape`, `pdf_text`, `pdf_image`, `image_ocr`, `json_path`, `yaml_path`,
  `xml_path`, `key_path`, `csv_cell` and `text_span`.

The document archetype library has 69 entries across HR, finance, sales/CRM,
healthcare, IT/engineering, management and operations. One archetype can render
as several formats; an invoice can be PDF, DOCX or XLSX without changing the
business content. The tested format/language matrix is in
[`docs/capability-matrix.md`](docs/capability-matrix.md).

### Language system (schema 2.1)

- **Central localization layer** (`v2/localization.py`) for titles, headings,
  table headers, sheet names, status values, notes, footers and formatting.
- **Per-attachment language**: a Thai DOCX can sit next to an English XLSX in
  one case. `prompt_language`, `content_languages`, `language_mode`,
  `language_coverage` and per-attachment `language` / `language_mix` record it.
- **True mixed documents**: bilingual headers such as `ชื่อ / name`, Thai prose
  with English technical terms, and English machine keys with Thai comments.
  `attachment.language_check` counts Thai and Latin script and the evaluator
  gates on it.
- **Thai formatting**: Buddhist-era or Gregorian dates (`thai_date_mode`),
  THB currency (`currency_mode`) and Thai labels. English documents stay
  English.
- **PDF and images are Latin-only** (built-in WinAnsi / bitmap fonts). Thai
  requests for those renderers are routed to English and record
  `language_routing: pdf_latin_only` or `<ext>_latin_only`. The renderers raise
  on non-Latin text instead of writing `?`.

Prompt/attachment language combinations are measured in
`reports/v2/evaluation.json` under `language_matrix` (for example
`th->mixed`), not assumed.

### Scenario plan and cross-file consistency

Every case builds one `ScenarioPlan` before its attachments: organisation,
people, customers, hosts, database endpoint, internal URL, incident/request/
ticket/invoice IDs, transaction references, dates and amounts. Builders draw
shared values from it, so `app.log`, `prod.env` and `incident_report.docx` tell
the same story.

The case records:

- `cross_file_links`: shared entities that occur in two or more attachments;
- `bundle`: `single_file`, `multi_file`, `same_archetype`, `old_new` or
  `prompt_only`, with members and revision changes;
- `consistency_checks`: invoice arithmetic, invoice due date, payroll
  gross - tax = net, statement running balance, ordered log timestamps,
  structure reference resolution and cross-file identifiers;
- `structure_references`: prompts such as "ดู tab employee" or "หน้า 3" point at
  a sheet/page/section/row/slide that actually exists (or are marked invalid);
- `document_profile`: per-file structure (sections, tables, rows, sheets,
  slides, pages).

### v2 dataset layout

```
datasets/v2-sample/
├── manifest.json
├── cases.jsonl
├── all.json
├── stats.json
├── train.jsonl validation.jsonl test.jsonl
├── ground_truth/entities.jsonl
└── attachments/TC-.../file.ext
```

`manifest.json` records schema/generator versions, fixed dataset epoch, seed,
profile, file/domain/language/persona/difficulty distributions, verification
status, config/policy hashes and SHA-256 for every generated artifact and
attachment. There is no wall-clock timestamp, so the same config + seed
reproduces the case JSON and attachment bytes.

### v2 measured sample

The committed `datasets/v2-sample` has 72 cases, 62 attachment files, 32
archetypes, 16 personas, 19 intents and 9 file types. `reports/v2/evaluation.json`
records measured values: schema validity 1.0, prompt span accuracy 1.0, file
open rate 1.0, extraction accuracy 1.0, entity location accuracy 1.0,
exact/near/document duplicate rates 0.0, negative share 0.1528, multi-domain
share 0.1389, attachment share 0.6389 and 8 OCR-oriented cases. Of 72 cases, 64
are fully verified and 8 are `verified_partial` because image/scanned annotations
are render-layout verified, not OCR-verified.

Language is measured, not assumed: prompt languages are Thai 39, English 19,
mixed 14; attachment languages are Thai 12, English 29, mixed 21; 12 distinct
prompt→attachment language pairs appear. 16 cases carry a structure reference
(every one resolves), 6 cases have cross-file links (20 links), and all
consistency checks pass. 12 cases are multi-file, 3 are same-archetype or
old/new bundles, and 26 are prompt-only.

### v2 limitations

These are deliberate and documented rather than hidden:

- PDF content is English/Latin because the standard-library PDF writer uses
  built-in WinAnsi fonts. Thai PDF requests are routed to English DOCX/XLSX/TXT
  and record `language_routing`; the PDF renderer raises rather than replacing
  Thai glyphs with `?`.
- Images use a bitmap Latin font. Thai image scenarios are routed to English
  and record `language_routing`; image/scanned-PDF OCR is verified at layout
  level, not with a third-party OCR engine.
- Rotated OCR images keep pre-render bounding boxes (`bbox_space:
  pre_render`).
- PPTX speaker notes and native PowerPoint tables are not emitted yet.
- YAML/TOML/INI/ENV verification uses the generator's strict subset parser.
- Archives, password-protected files, audio, video and executables are out of
  scope.
- `report-v2` reports what it measured; a `verified_partial` case must not be
  treated as OCR accuracy evidence.
- Cross-file consistency is checked against generated annotations and the
  scenario plan; no downstream gateway is executed.

## What it produces

| Domain | Example entity types |
|---|---|
| PII | Thai national ID (checksum-valid), Thai name, phone, email, address, postal code, date of birth, personal IP, GPS, vehicle registration, bank account, health data, patient ID, passport |
| Payment | Test-BIN card numbers (Luhn-valid), expiry, CVV, cardholder name, bank account, transaction reference, authorization code, payment token, gateway credential |
| Secrets | API keys, access/refresh tokens, OAuth secrets, JWTs, passwords, DB credentials, connection strings, SSH/TLS keys, cloud keys, service-account credentials, webhook secrets, encryption keys, env/config secrets |
| Infrastructure | Internal IPv4/IPv6, private networks, hostnames, DNS, URLs, topology, endpoints, firewall rules, routing, Kubernetes, Docker, cloud resource IDs, DB endpoints, Terraform, deployment configs, logs, inventories, blueprints, metadata |

Prompt coverage:

- **Short** — one-line requests such as checking a customer ID, sending an API
  key to an external model, or summarizing a card payment.
- **Medium** — support emails, payment verification, debugging, sysadmin
  questions, document summaries, tables and JSON payloads.
- **Long** — enterprise reports, chat transcripts, meeting notes, architecture
  documents, log exports, SQL dumps and Kubernetes manifests.
- **Contextual** — values inside quoted text, signatures, code fences, logs,
  JSON/YAML, tables and multi-step instructions.
- **Mixed-domain** — PII + payment, secrets + infrastructure, three domains, and
  all four domains in one prompt.
- **Negative / ambiguous** — ordinary business IDs, invalid checksums, Luhn
  failures, placeholders, public IPs and documentation ranges, annotated as
  lookalikes so false positives can be measured.

Every case is classified by domain, entity type, language, prompt length,
prompt style, structure, context complexity, detection mode, difficulty (1–5),
polarity, single/multi-domain, edge-case and adversarial flags.

## Dataset format

`generate` writes:

```
datasets/sample/
├── all.jsonl
├── train.jsonl
├── validation.jsonl
├── test.jsonl
├── all.json
├── stats.json
└── manifest.json
```

Each JSONL row is one case:

```json
{
  "test_id": "pgt-trn-00003",
  "prompt": "Summarize payment 4111112399105924 for the customer.",
  "language": "en",
  "domains": ["payment"],
  "entities": [{
    "domain": "payment",
    "entity_type": "payment_card_number",
    "character_start": 18,
    "character_end": 34,
    "exact_entity_value": "4111112399105924",
    "detection_expected": true,
    "classification_expected": "payment_card_number",
    "valid": true
  }],
  "policy_decision_expected": "TOKENIZE",
  "action_expected": {"payment_card_number": "TOKENIZE"},
  "routing_expected": "external",
  "transformation_expected": [{"entity_type": "payment_card_number", "action": "TOKENIZE"}],
  "output_leakage_check_expected": true,
  "token_restoration_expected": "authorized_context_only",
  "audit_log_expected": {
    "record_fields": ["test_id", "policy_scenario", "entity_types", "actions"],
    "forbidden_fields": ["exact_entity_value"]
  },
  "difficulty": 1,
  "prompt_length_class": "short",
  "prompt_style": "short",
  "polarity": "positive",
  "split": "train",
  "verification_status": "verified_spans",
  "char_offset_convention": "unicode_codepoints_0_based_end_exclusive"
}
```

The full schema is [`schemas/testcase.schema.json`](schemas/testcase.schema.json).
`manifest.json` records the seed, dataset/generator version, config and policy
hashes, per-file SHA-256, and the split-to-template map used to prove leakage
isolation. Artifacts contain no timestamps, so the same config and seed produce
byte-identical files.

## Configuration

`configs/default.json` controls:

- seed, total sample count, train/validation/test ratios
- domain, language, length, difficulty and entity-density distributions
- negative and multi-domain ratios
- near-duplicate threshold
- quality-gate thresholds

`configs/policy.default.json` controls:

- action precedence (`ALLOW → MASK → TOKENIZE → REDACT → LOCAL_ONLY → BLOCK`)
- policy scenarios and their routing / minimum action
- per-domain and per-entity-type rules

The default policy is an **illustrative test configuration**, not legal advice.
Replace it with your organisation's policy before evaluating a real gateway.

## Policy expectations

For every detected entity, all matching rules are evaluated and the strictest
action wins. Scenario floors (`min_action`) raise detected entities further.
The case-level `policy_decision_expected` is the strictest entity action; per
entity actions remain available in `action_expected` and
`transformation_expected`. Routing is `local` for `LOCAL_ONLY`, `blocked` for
`BLOCK`, otherwise the scenario routing. With no detected entities the result is
`ALLOW`.

The shipped policy deliberately exercises every action, including conflicting
rules where the strictest must prevail.

## Quality gates and current results

`evaluate` checks: schema validity, span accuracy, reproducibility, exact and
near duplicate rates, domain/language/length/difficulty/entity coverage,
negative and multi-domain ratios, all-action coverage, and split integrity
(including cross-split near-duplicates). It writes `reports/evaluation.json`
and `reports/evaluation.md`.

Latest run on the committed sample (`seed 7`, 140 cases):

| Gate | Result |
|---|---|
| Schema validity / span accuracy / reproducibility | PASS (1.0 / 1.0 / byte-identical) |
| Exact / near duplicate rate | PASS (0.0 / 0.0 at 0.98 threshold) |
| Domain coverage | PASS (PII .45, payment .28, secrets .22, infrastructure .21) |
| Language coverage | PASS (Thai .48, English .26, mixed .26) |
| Length coverage | PASS (short .37, medium .39, long .24) |
| Difficulty 1–5 | PASS (.37 / .11 / .24 / .22 / .06) |
| Entity-type coverage | PASS (31 types) |
| Negative ratio | PASS (.21 vs .20 target) |
| Multi-domain share | PASS (.29) |
| All six actions present | PASS |
| Split integrity | PASS (no family or near-duplicate crosses splits) |

See [`docs/evaluation-report.md`](docs/evaluation-report.md) and
[`reports/evaluation.md`](reports/evaluation.md) for the generated report.

Automated suite: **130 tests pass** (`python -m unittest discover -s tests -t .`).
The suite covers entity validity and safety, exact spans, every template in all
three languages, policy precedence, validation failures, annotation repair,
generator reproducibility/dedup/splits, security scans, schema agreement, the
CLI, every v2 file renderer's round trip, v2 distribution/persona/OCR cases,
localization, per-attachment language, mixed-script checks, cross-file
consistency, arithmetic, old/new bundles, structure references, v2 schema
agreement and v2 security scans.

## Safety

- Emails use `example.com/org/net`; hosts use `.internal` / `.example`.
- IPv4 uses RFC 1918 or RFC 5737 ranges; IPv6 uses ULA `fd00::/8`.
- Cards use documented test BINs and are Luhn-valid; invalid card lookalikes
  fail Luhn.
- AWS-like keys contain `FAKE`/`EXAMPLE`; PEM blocks use
  `EXAMPLE FAKE ... PRIVATE KEY`, which real parsers reject.
- JWTs are HS256-shaped but have `example-fake-signature`.
- No network calls, telemetry, or third-party dependencies.

Read [`SECURITY.md`](SECURITY.md) before generating data for a shared
environment. Generated datasets are synthetic but may still trip scanners;
label them clearly.

## Project layout

```
SKILL.md                     Agent Skill instructions
configs/                     dataset + policy configuration
schemas/testcase.schema.json JSON Schema
src/privacy_gateway_testgen/ package
  entities/                  four-domain + lookalike factories
  templates.py               prompt library
  builder.py                 span-recording builder
  generator.py               dataset engine, dedup, splits, export
  policies.py                precedence + scenario resolution
  validation.py              schema/span/policy validation
  evaluation.py              quality gates
  annotations.py             imported-annotation verification
  textsim.py                 duplicate/leakage similarity
  cli.py                     command line interface
  v2/                        file-aware schema 2.1 generator
    localization.py          Thai/English/mixed labels and formatting
    scenario.py              shared people, hosts, IDs, transactions
    archetypes.py            business documents independent of format
    renderers/               real TXT/CSV/JSON/Office/PDF/image bytes
    extract.py               reopen/parse/locate verification
    generate.py              targets, bundles, splits, export
    evaluate.py              measured gates and language/consistency metrics
tests/                       unittest suite
datasets/sample/             generated sample dataset
reports/                     latest evaluation
docs/                        architecture, acceptance criteria, evaluation
evals/                       skill-behavior evaluation prompts
```

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -t . -v
PYTHONPATH=src python -m privacy_gateway_testgen evaluate --config configs/default.json --out reports
```

Add a factory or template, run the tests, regenerate the sample, and re-run the
gates. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`docs/architecture.md`](docs/architecture.md).

## Limitations

- Validation/test splits are template-family-disjoint, so a small dataset has
  fewer families per split. Add templates when split diversity matters.
- Distribution weights are **preferences, not exact quotas**: length and
  difficulty are coupled to the available template families, so a run can drift
  from the configured weights. `evaluation.json` reports configured-vs-measured
  deltas; the gates enforce coverage, not every weight.
- Negative lookalikes may still be flagged by pattern-only detectors; that is
  the intended false-positive probe, not a label error.
- Thai names, addresses and organisations are synthetic combinations that may
  coincidentally resemble real entities.
- Only documented test card BINs are used. **No PCI DSS compliance is claimed.**
- The default policy is illustrative, not legal advice.
- No performance or latency claims are made.
- LLM-authored prompts are not produced by this tool; imported cases need the
  `verify` stage and human semantic review.

## License

MIT — see [`LICENSE`](LICENSE).
