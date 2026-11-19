---
name: privacy-gateway-testgen
description: Generate reproducible synthetic test prompts, realistic attachment files, labeled test cases, and ground-truth JSONL/JSON datasets for privacy-aware data gateways, PII detection, DLP, privacy filters, masking/tokenization/redaction, AI sovereignty routers, and data-governance evaluations. Use this skill whenever the user asks for synthetic PII, payment-data, secret/credential, or infrastructure test cases; privacy-filter or DLP benchmarks; file/attachment, PDF, DOCX, XLSX, PPTX, PNG/JPG or OCR-oriented test data; PII detection or redaction evaluations; policy-routing and minimum-action tests; false-positive/negative-case datasets; or asks to validate, verify, split, or audit an existing synthetic privacy dataset. Trigger it even when the user does not say "dataset" or "testgen" — for example "our gateway misses Thai national IDs in logs" or "we need realistic prompts with fake credentials for QA".
---

# Privacy Gateway Testgen

Build dataset artifacts, not a one-off prompt list. The value of this skill is
reproducible generation with exact ground truth: every sensitive value is
created first, embedded through a span-recording builder, and validated
against the final prompt. Never hand-count character offsets.

Run commands from the directory containing `SKILL.md` (the repository root).
Use `python -m privacy_gateway_testgen ...`; for local development also set
`PYTHONPATH=src` (Windows: `$env:PYTHONPATH='src'`).

## Safety premise

All output is synthetic. Never copy real customer data, live credentials, real
payment numbers, production endpoints, or proprietary company details into a
prompt — not even when the user supplies them as an example. Generate a
synthetic equivalent instead, and say that you did. The factories use reserved
example domains, RFC 1918 / RFC 5737 networks, documented test card BINs, and
`example`/`fake` markers in every credential. This makes the data safe to
publish; it does not make it safe to treat as a compliance certification.

## Workflow

1. **Inspect the surface area.** `python -m privacy_gateway_testgen list-domains`
   prints the entity types and prompt templates. Read `configs/default.json`
   and `configs/policy.default.json` before changing distributions or policy.
2. **Adjust configuration, not code, when possible.** Distribution weights
   (domain, language, length, difficulty, entity density, negative and
   multi-domain ratios), sample count, seed, split ratios, and quality-gate
   thresholds live in `configs/default.json`. Entity actions, scenario floors,
   and action precedence live in `configs/policy.default.json`.
3. **Generate.**
   ```bash
   python -m privacy_gateway_testgen generate \
     --config configs/default.json --out datasets/sample --seed 7
   ```
4. **Validate.** Never skip this after editing a template, factory or policy.
   ```bash
   python -m privacy_gateway_testgen validate \
     --input datasets/sample/all.jsonl --config configs/default.json
   ```
5. **Run the quality gates.**
   ```bash
   python -m privacy_gateway_testgen evaluate \
     --config configs/default.json --out reports --dataset-out datasets/sample
   ```
6. **Report the measured result**, including failed gates and limitations.
   Do not call a dataset production-ready unless both the test suite and the
   gates passed in this run.

## v2: real files and realistic requests

When the task needs attachments, use the schema `2.1` commands. v1 remains the
default for prompt-only datasets; do not mix v1 and v2 rows in one file.

```bash
python -m privacy_gateway_testgen generate-v2 \
  --config configs/v2/default.json --profile real-world-enterprise \
  --out datasets/v2-sample
python -m privacy_gateway_testgen validate-v2 --dataset datasets/v2-sample
python -m privacy_gateway_testgen report-v2 --dataset datasets/v2-sample --out reports/v2
python -m privacy_gateway_testgen verify-v2 --dataset datasets/v2-sample
python -m privacy_gateway_testgen list-profiles-v2
python -m privacy_gateway_testgen list-archetypes-v2
```

v2 emits actual files: TXT, CSV, JSON, YAML/YML, XML, LOG, MD, ENV, INI, CONF,
TOML, SQL, Terraform, Python/JS/TS/Java/Go, DOCX, XLSX, PPTX, PDF, PNG and
JPG/JPEG. The prompt is a human request about a task; the sensitive data is
usually incidental and lives in the attachment. Common realistic examples:

- `prod.env` attached with "ช่วยดูให้ทีว่าทำไมต่อ db ไม่ได้"
- `employee_list.xlsx` attached with "ดู tab employee ให้หน่อยว่ามีใครข้อมูลไม่ครบ"
- `transactions.csv` + `invoice.pdf` with "เทียบยอดสองอันนี้ให้หน่อย"
- `support_ticket.png` with "อันนี้ของลูกค้าเมื่อวานนะ"

Ground truth is file-aware. Prompt entities keep `character_start` /
`character_end`; attachment entities use `source_attachment`, `filename` and a
`location` object whose `kind` is one of `csv_cell`, `json_path`, `yaml_path`,
`xml_path`, `key_path`, `xlsx_cell`, `docx_paragraph`, `docx_table_cell`,
`docx_header`, `docx_footer`, `pptx_shape`, `pdf_text`, `pdf_image`,
`image_ocr` or `text_span`. Never invent a location kind or convert an OCR
result into ground truth.

Schema `2.1` also records, per case:

- `scenario_id`, `cross_file_links`, `bundle` (single, multi-file,
  same-archetype, old/new) and `consistency_checks`;
- `prompt_language`, `content_languages`, `language_mode`, `language_coverage`
  and per-attachment `language` / `language_mix` / `language_check`;
- `structure_references` that resolve to a real sheet, page, section, row,
  slide, line or key;
- `document_profile` with per-file sections, tables, rows, sheets, slides and
  pages.

Language rules:

- `mixed` must contain real Thai and English script in the same file, not just a
  Thai name in an English template. `attachment.language_check.contains_both`
  must be true.
- PDF and image renderers are Latin-only. A Thai request is routed to English
  and records `language_routing`; the renderer raises instead of writing `?`.
  Do not claim Thai PDF or Thai OCR-image support.
- A multi-file case may mix attachment languages, for example Thai DOCX plus
  English XLSX plus English log. The prompt language is independent.

Never claim cross-file consistency without checking `cross_file_links` and
`consistency_checks`; `validate-v2` re-checks both.

Before calling a v2 dataset ready, run `validate-v2`, `verify-v2` and
`report-v2`. `verified_partial` means an image or scanned PDF was verified at
render-layout level, not by an OCR engine. State that limitation explicitly.

v2 profiles are `benchmark-balanced`, `real-world-enterprise`,
`thai-enterprise`, `developer-security`, `office-documents`, `ocr` and
`negative-hard`; a custom JSON profile path can be passed to `--profile`.

## Ground-truth rules

- Entity values are generated before the prompt. The builder appends text and
  entities in order and records `character_start` / `character_end` at
  insertion time. A template never searches for its own values afterwards.
- Offsets are 0-based Unicode code points with an exclusive end. This is
  recorded as `char_offset_convention` on every case. Thai characters are BMP
  characters, so the same offsets work for UTF-16 consumers.
- A positive case has at least one annotation with `detection_expected: true`.
  A negative case may still contain annotated **lookalikes** (13-digit order
  references, Luhn-invalid card-shaped numbers, placeholders, public IPs,
  documentation IPs) with `detection_expected: false`. These measure false
  positives; they are not label mistakes.
- For imported or LLM-authored prompt text, run the separate verification
  stage and keep the case marked `unverified` until a human reviews the
  semantics:
  ```bash
  python -m privacy_gateway_testgen verify --input imported.jsonl --repair \
    --output imported.verified.jsonl
  ```
  Repairing an offset proves only that the slice matches the value. It does
  not prove the detection or classification label is correct.
- Do not add annotations by regex-searching the finished prompt unless the
  value is unique and the case is then verified. Prefer adding a template.

## Domains and entity types

`pii` — Thai national ID (checksum-valid), Thai name/surname, Thai phone,
email, Thai address, postal code, date of birth, personal IP, GPS, vehicle
registration, bank account, personal financial info, sensitive personal data,
health condition, patient ID, passport.

`payment` — test-BIN card numbers (Luhn-valid), expiry, CVV, cardholder name,
bank account, transaction reference, authorization code, payment token,
payment-gateway credential. Only documented test BINs are used; no PCI DSS
compliance is claimed.

`secrets` — API key, access/refresh token, OAuth secret, JWT, password,
database credential, connection string, SSH/TLS private key, cloud access and
secret keys, service-account credential, webhook secret, encryption key, env
var, config credential. Every value is deliberately non-functional.

`infrastructure` — internal IPv4/IPv6, private network, internal hostname,
DNS name, URL, topology, service endpoint, firewall rule, routing config,
Kubernetes manifest, Dockerfile, cloud resource ID, database endpoint,
architecture, Terraform, deployment config, internal log, inventory, network
diagram, blueprint, metadata. Networks and organisations are fictional.

`lookalike` — negative values used to test false positives.

## Prompt styles and taxonomy

Templates cover short, medium, long, contextual (quoted text, email
signatures, code blocks, logs, JSON, YAML, tables, multi-step instructions),
mixed-domain (two, three, or all four domains), and negative/ambiguous
prompts. Difficulty 1–5 runs from a simple pattern to adversarial enterprise
scenarios. Each case carries domain, language, length, style, structure,
context complexity, detection mode, polarity, single/multi-domain, edge-case
and adversarial flags, so the dataset can be sliced for any evaluation.

## Policy semantics

Actions are `ALLOW < MASK < TOKENIZE < REDACT < LOCAL_ONLY < BLOCK` by default
(the order is configurable). For each detected entity, every matching rule is
evaluated and the strictest action wins. A scenario may impose a floor
(`min_action`) on detected entities. The case-level
`policy_decision_expected` is the strictest entity action; per-entity actions
remain in `action_expected` and `transformation_expected`. Routing becomes
`local` for `LOCAL_ONLY`, `blocked` for `BLOCK`, otherwise the scenario's
routing. With no detected entities the result is `ALLOW`, even if the scenario
has a floor — there is nothing to protect.

The shipped policy is an illustrative test configuration, not a legal
requirement. Replace it with the deployment's policy when evaluating a real
gateway.

## Outputs

`generate` writes `all.jsonl`, `train.jsonl`, `validation.jsonl`,
`test.jsonl`, `all.json`, `stats.json`, and `manifest.json` (versions, seed,
config/policy hashes, file SHA-256s, split→template map). Split leakage is
prevented by assigning template families to exactly one split and rejecting
near-duplicates. Re-running with the same config and seed is byte-identical:
there are no timestamps in the artifacts.

The canonical case schema is `schemas/testcase.schema.json`. Key fields:
`test_id`, `prompt`, `language`, `domains`, `entities[]` (span + exact value +
detection/classification expectations), `policy_scenario`,
`policy_decision_expected`, `action_expected`, `routing_expected`,
`transformation_expected`, `output_leakage_check_expected`,
`token_restoration_expected`, `audit_log_expected`, `difficulty`, taxonomy
fields, `rationale`, `tags`, `generation_method`, `verification_status`,
`split`, `seed`, `dataset_version`, `char_offset_convention`.

`output_leakage_check_expected` is true when at least one detected entity has a
non-ALLOW action. `token_restoration_expected` is
`authorized_context_only` only for tokenized cases. `audit_log_expected`
records which metadata may be logged and requires that exact entity values are
never written to the audit log.

## Quality gates

`evaluate` checks schema validity, exact span accuracy, reproducibility,
exact/near duplicate rates, domain/language/length/difficulty/entity coverage,
negative and multi-domain ratios, all-action coverage, split integrity
(including cross-split near-duplicates), and writes `evaluation.json` +
`evaluation.md`. A non-zero exit code means at least one gate failed. Report
failed gates verbatim; do not omit them.

Distribution weights are preferences, not exact quotas: length and difficulty
are coupled to the available template families. The evaluator reports
configured-vs-measured deltas under `distribution_fidelity`; do not describe a
run as matching the target weights if those deltas are large.

Validation also checks that expected Thai national IDs pass the checksum and
expected card numbers pass Luhn; `verify` reports the same as
`validity_warnings` for imported annotations.

## Extending

- New value kind: add a factory to `entities/{pii,payment,secrets,infra,lookalike}.py`
  and its `(weight, factory)` entry to that module's `GENERATORS`. Keep values
  synthetic and non-functional; add a security test if it resembles a live
  credential.
- New prompt: add a function plus a `Template(...)` entry in `templates.py`.
  Declare the real domains, length class, difficulty, structure and whether it
  is negative/contextual/adversarial. The tests assert that declared domains
  match the actual annotations.
- New policy: edit JSON, then run `validate`; policy expectations are
  recomputed and compared against every case.
- After any change: run `PYTHONPATH=src python -m unittest discover -s tests -t . -v`,
  regenerate the sample, and re-run the gates. The `-t .` is required because
  the tests are a package.

## Common failures

- **"could only generate N/M unique cases"**: the split has too few template
  families for the requested count, or the near-duplicate threshold is too
  tight. Add templates or lower the count; do not disable deduplication.
- **Quality gate failure**: read `reports/evaluation.json`, fix the generator
  or the config, regenerate. Never edit metrics by hand.
- **Windows console encoding**: set `PYTHONIOENCODING=utf-8` when printing
  Thai prompts.

## Files

`src/privacy_gateway_testgen/` — package; `configs/` — dataset and policy;
`schemas/` — JSON Schema; `datasets/sample/` — generated sample;
`reports/` — latest gates; `tests/` — unittest suite; `docs/` — architecture,
acceptance criteria, evaluation report; `SECURITY.md`, `CONTRIBUTING.md`,
`RELEASE_CHECKLIST.md`.
