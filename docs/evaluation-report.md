# Evaluation Report

- Date: 2026-11-20
- Environment: Windows, Python 3.13, standard library only
- v1 dataset version: `0.1.0`, seed `7`, 140 cases
- v2 dataset version: `2.1.0`, seed `7`, profile `real-world-enterprise`, 72 cases
- Package version: `0.3.0`

## Commands executed

```bash
PYTHONPATH=src python -m unittest discover -s tests -t . -v
PYTHONPATH=src python -m privacy_gateway_testgen evaluate \
  --config configs/default.json --out reports --dataset-out datasets/sample
PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 \
  --config configs/v2/default.json --profile real-world-enterprise \
  --out datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 \
  --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen verify-v2 \
  --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen report-v2 \
  --dataset datasets/v2-sample --out reports/v2 --check-reproducible
```

Raw results: `reports/evaluation.json`, `reports/evaluation.md`,
`reports/v2/evaluation.json`, `reports/v2/evaluation.md`,
`reports/v2/verification.json`.

## Automated tests

**Result: PASS - 130 tests, 0 failures, 0 errors** (about 42 seconds).

| Area | What it covers |
|---|---|
| v1 core | entity validity/safety, spans, every template in three languages, policy precedence, validation, annotation repair, reproducibility, dedup/splits, security, schema, CLI |
| v2 renderers | every supported format renders, reopens and verifies; macro-free OOXML; no active PDF content |
| v2 language (2.1) | Thai labels, mixed-script documents, per-attachment language, PDF/image routing, Thai date/currency formatting, language matrix |
| v2 consistency (2.1) | shared scenario values, invoice/payroll/statement arithmetic, cross-file links, old/new bundles, structure references, tamper rejection |
| schema 2.1 | generated cases carry the additive fields; 2.0 remains valid |

## v1 measured gates

All configured gates pass on the committed `datasets/sample`:

| Gate | Result |
|---|---|
| Schema validity / span accuracy / reproducibility | PASS (1.0 / 1.0 / byte-identical) |
| Exact / near duplicate rate | PASS (0.0 / 0.0 at 0.98) |
| Domain coverage | PASS (PII .45, payment .2786, secrets .2214, infrastructure .2071) |
| Language coverage | PASS (Thai .4786, English .2643, mixed .2571) |
| Length coverage | PASS (short .3714, medium .3929, long .2357) |
| Difficulty 1–5 | PASS (.3714/.1143/.2357/.2214/.0571) |
| Entity-type coverage | PASS (31 types) |
| Negative ratio | PASS (.2143 vs .20 target) |
| Multi-domain share | PASS (.2857) |
| All six actions present | PASS |
| Split integrity | PASS |

## v2.1 measured gates

`datasets/v2-sample`: 72 cases, 62 attachment files, 32 archetypes, 16 personas,
19 intents, 9 file types.

All configured gates pass:

| Gate | Measured |
|---|---|
| Schema validity | 1.0 |
| Prompt span accuracy | 1.0 |
| File open rate | 1.0 |
| Entity location accuracy | 1.0 |
| Extraction accuracy | 1.0 |
| Exact / near / document duplicate rate | 0.0 / 0.0 / 0.0 |
| File type coverage | 9 (csv, docx, jpg, json, md, pdf, png, txt, xlsx) |
| Archetype / persona / intent coverage | 32 / 16 / 19 |
| Prompt language coverage | Thai 39, English 19, mixed 14 |
| Attachment language coverage | Thai 12, English 29, mixed 21 |
| Prompt→attachment language matrix | 12 pairs; mixed-script rate 1.0 |
| Structure reference resolution | 16 cases, 1.0 resolved |
| Multi-file share | 0.1667 (12 cases, including 2 old/new and 1 same-archetype bundle) |
| Cross-file link coverage | 6 cases, 20 links, consistency 1.0 |
| Consistency checks | all pass (invoice, payroll, statement, timestamps, structure, cross-file) |
| Negative / multi-domain / attachment share | 0.1528 / 0.1389 / 0.6389 |
| OCR cases | 8 (`verified_partial`; layout-verified, no OCR accuracy claim) |
| Opening / repeated phrase / archetype concentration | 0.0139 / 0.1389 / 0.1111 |
| Reproducibility | True (same seed + config reproduce case JSON and attachment bytes) |

Verification status: 64 `verified`, 8 `verified_partial`, 0 `unverified`.

## Interpretation

The numbers are measured from the committed datasets. They do not claim OCR
accuracy, a downstream detector's accuracy, gateway benchmark performance, or
production readiness. PDF/image Thai support is explicitly not claimed; those
requests are routed and recorded. The default policy is illustrative, not legal
advice. See `docs/capability-matrix.md` and `docs/v2-design.md` for the exact
boundary.

## Conclusion

For **v0.3.0**, the repository's automated tests and all configured quality gates
pass, every attachment reopens and verifies, and the v2.1 sample contains
measured language, cross-file, structure and consistency evidence. The tool is
ready for public testing as a synthetic testcase generator. It does not certify a
gateway, a legal policy, or PCI DSS compliance.
