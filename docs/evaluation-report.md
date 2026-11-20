# Evaluation Report

- Date: 2026-11-20
- Environment: Windows, Python 3.13, standard library only
- v1 dataset version: `0.1.0`, seed `7`, 140 cases
- v2 dataset version: `2.1.1`, seed `21`, profile `benchmark-balanced`, 72 cases
- Package version: `0.3.1`

## Commands executed

```bash
PYTHONPATH=src python -m unittest discover -s tests -t . -v
PYTHONPATH=src python -m privacy_gateway_testgen evaluate \
  --config configs/default.json --out reports --dataset-out datasets/sample
PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 \
  --config configs/v2/default.json --profile benchmark-balanced \
  --out datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 \
  --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen verify-v2 \
  --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen report-v2 \
  --dataset datasets/v2-sample --out reports/v2 --check-reproducible
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 \
  --dataset datasets/compat/v2.0-sample
```

Reports were additionally generated under `PYTHONHASHSEED=1` and
`PYTHONHASHSEED=424242`; the three report files compared byte-identical.

Raw results: `reports/evaluation.json`, `reports/evaluation.md`,
`reports/v2/evaluation.json`, `reports/v2/evaluation.md`,
`reports/v2/verification.json`, `datasets/v2-sample/manifest.json`.

## Automated tests

**Result: PASS - 167 tests, 0 failures, 0 errors** (about 57 seconds).

| Area | What it covers |
|---|---|
| v1 core | entity validity/safety, spans, every template in three languages, policy precedence, validation, annotation repair, reproducibility, dedup/splits, security, schema, CLI |
| v2 renderers | every supported format renders, reopens and verifies; macro-free OOXML; no active PDF content |
| v2 language (2.1) | measured script shares, Thai labels, mixed-script documents, per-attachment language, per-attachment Latin routing, Thai formatting, language matrix |
| v2 consistency (2.1) | shared scenario values, invoice/payroll/statement arithmetic, linked financial values, cross-file links, old/new bundles, bundle relationship evidence, structure references, tamper rejection |
| v2.1.1 correctness | log timeline parsing and ordering, image atomic entity ground truth, language-share thresholds, no placeholder people, deterministic reports across hash seeds, compound-label localization, Thai address coherence, Thai typo conservatism, prompt-composition quality, N/A consistency semantics, schema 2.0 fixture, CI gate coverage |
| schema 2.1 | generated cases carry the additive fields; 2.0 remains valid |

## v1 measured gates

All configured gates pass on the committed `datasets/sample`:

| Gate | Result |
|---|---|
| Schema validity / span accuracy / reproducibility | PASS (1.0 / 1.0 / byte-identical) |
| Domain coverage | PASS (PII .4571, payment .2571, secrets .2286, infrastructure .2571) |
| Language coverage | PASS (Thai .5000, English .2643, mixed .2357) |
| Length coverage | PASS (short .3929, medium .3857, long .2214) |
| Difficulty 1–5 | PASS (.3929/.1214/.2214/.2071/.0571) |
| Entity-type coverage | PASS (32 types) |
| Negative ratio | PASS (.1857) |
| Multi-domain share | PASS (.2786) |
| All six actions present | PASS |
| Split integrity | PASS |

## v2.1.1 measured gates

`datasets/v2-sample`: 72 cases, 82 attachment files, 21 file types,
3 attachment languages.

All configured gates pass:

| Gate | Measured |
|---|---|
| Schema validity | 1.0 |
| Prompt span accuracy | 1.0 |
| File open rate | 1.0 |
| Entity location accuracy | 1.0 |
| Extraction accuracy | 1.0 |
| Exact / near / document duplicate rate | 0.0 / 0.0 / 0.0 |
| File type coverage | 21 |
| Prompt language coverage | Thai 27, English 21, mixed 24 |
| Attachment language coverage | Thai 30, English 48, mixed 4 |
| Prompt→attachment language matrix | 11 pairs; mixed-script rate 1.0 |
| Language share check | 0 attachments below their declared threshold |
| Residual English labels in Thai documents | 0 |
| Structure reference resolution | 28 cases, 30 references, 1.0 resolved |
| Multi-file share | 0.2361 (17 cases, including 8 same-archetype and 5 old/new bundles) |
| Cross-file link coverage | 17 cases, 77 links, consistency 1.0 |
| Consistency checks | 78 passed, 264 not_applicable, 0 failed, 0 not_evaluated |
| Negative / multi-domain / attachment share | 0.1944 / 0.2222 / 0.7917 |
| OCR cases | 4 (`verified_partial`; layout-verified, no OCR accuracy claim) |
| Prompt form concentration | 9 prompt-only forms; top share 0.2667 |
| Opening / repeated phrase / archetype concentration | 0.0278 / 0.0833 / 0.0833 |
| Reproducibility | True (same seed + config reproduce case JSON and attachment bytes) |

Verification status: 68 `verified`, 4 `verified_partial`, 0 `unverified`.
`benchmark_ready: true`, 68 benchmark-safe cases, 4 excluded (layout-only OCR).

## Interpretation

The numbers are measured from the committed datasets. They do not claim OCR
accuracy, a downstream detector's accuracy, gateway benchmark performance, or
production readiness. PDF/image Thai support is explicitly not claimed; those
requests are routed per attachment and recorded. The default policy is
illustrative, not legal advice. Synthetic phones, national-ID-shaped values and
bank accounts can coincide with real identifiers; see the collision-risk section
in `SECURITY.md`. See `docs/capability-matrix.md` and `docs/v2-design.md` for the
exact boundary.

## Conclusion

For **v0.3.1**, the repository's automated tests and all configured quality gates
pass, every attachment reopens and verifies, and the v2.1.1 sample contains
measured language, cross-file, structure, temporal and consistency evidence with
a computed `benchmark_ready` decision. The tool is ready for public testing as a
synthetic testcase generator. It does not certify a gateway, a legal policy, or
PCI DSS compliance.
