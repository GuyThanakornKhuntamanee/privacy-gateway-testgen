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

Automated suite: **73 tests pass** (`python -m unittest discover -s tests -t .`).
The suite covers entity validity and safety, exact spans, every template in all
three languages, policy precedence, validation failures, annotation repair,
generator reproducibility/dedup/splits, security scans, schema agreement, and
the CLI.

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
