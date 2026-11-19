# Evaluation Report

- Date: 2026-11-09
- Environment: Windows, Python 3.13.1, standard library only
- Dataset version: `0.1.0`
- Seed: `7`
- Cases: `140` (train 112 / validation 14 / test 14)

## Commands executed

```bash
PYTHONPATH=src python -m unittest discover -s tests -t . -v
PYTHONPATH=src python -m privacy_gateway_testgen evaluate \
  --config configs/default.json --out reports --dataset-out datasets/sample
```

Raw results: `reports/evaluation.json`, `reports/evaluation.md`, and the
generated sample in `datasets/sample/`.

## Automated tests

**v1 result: PASS - 73 tests, 0 failures, 0 errors** (about 3.6 seconds).

| Module | Tests | What it covers |
|---|---:|---|
| `test_annotations.py` | 5 | unique vs ambiguous repair, no silent fixes, semantic-unverified reporting, checksum warnings |
| `test_builder.py` | 3 | Thai/multiline offsets, adjacent entities, span ordering |
| `test_cli.py` | 5 | generate/validate/stats/evaluate/verify/list-domains, UTF-8 BOM input |
| `test_entities.py` | 10 | national-ID checksum, Luhn/test BINs, fake secrets/JWT/PEM, reserved domains, private ranges, every factory |
| `test_evaluation.py` | 5 | passing gates, tampered spans, duplicates, non-reproducibility, markdown report |
| `test_generator.py` | 12 | counts, IDs, validation, uniqueness, family isolation, reproducibility, stats, export, split overrides, domain distribution, leakage/restoration/audit expectations |
| `test_policies.py` | 7 | strictest action, scenario floor, ALLOW with no entities, custom order, invalid policy |
| `test_schema.py` | 3 | required fields/enums match validator, generated cases contain every required field |
| `test_security.py` | 9 | live-secret markers, fake AWS keys, reserved emails, fake/internal connection strings, test BINs, IPv4 ranges, PEM labels |
| `test_templates.py` | 6 | every template × 3 languages × spans/domains/length; all-four-domain template; entity-type breadth |
| `test_validation.py` | 8 | span tampering, enums/offsets, policy mismatch, duplicates, span accuracy, negative cases, checksum/Luhn semantic checks |

## Quality gates

**Overall: PASS** — every gate passed.

| Gate | Result | Value | Requirement |
|---|---|---|---|
| schema_validity | PASS | 1.0 | >= 1.0 |
| span_accuracy | PASS | 1.0 | >= 1.0 |
| exact_duplicate_rate | PASS | 0.0 | <= 0.0 |
| near_duplicate_rate | PASS | 0.0 | <= 0.05 (threshold 0.98) |
| domain:pii | PASS | 0.45 | >= 0.05 |
| domain:payment | PASS | 0.2786 | >= 0.05 |
| domain:secrets | PASS | 0.2214 | >= 0.05 |
| domain:infrastructure | PASS | 0.2071 | >= 0.05 |
| language:th | PASS | 0.4786 | >= 0.08 |
| language:en | PASS | 0.2643 | >= 0.08 |
| language:mixed | PASS | 0.2571 | >= 0.08 |
| length:short | PASS | 0.3714 | >= 0.08 |
| length:medium | PASS | 0.3929 | >= 0.08 |
| length:long | PASS | 0.2357 | >= 0.08 |
| difficulty:1 | PASS | 0.3714 | >= 0.04 |
| difficulty:2 | PASS | 0.1143 | >= 0.04 |
| difficulty:3 | PASS | 0.2357 | >= 0.04 |
| difficulty:4 | PASS | 0.2214 | >= 0.04 |
| difficulty:5 | PASS | 0.0571 | >= 0.04 |
| entity_type_coverage | PASS | 31 | >= 25 |
| negative_ratio | PASS | 0.2143 | 0.2 ± 0.12 |
| multi_domain_share | PASS | 0.2857 | >= 0.12 |
| action_coverage | PASS | ALLOW, MASK, TOKENIZE, REDACT, LOCAL_ONLY, BLOCK | all actions |
| split_integrity | PASS | no family / exact-prompt / near-duplicate leakage | clean |
| reproducibility | PASS | byte-identical second run | required |

### Coverage detail

- Actions: `ALLOW 30, BLOCK 31, LOCAL_ONLY 29, MASK 13, REDACT 33, TOKENIZE 4`.
- Structures: unstructured 69, code 16, JSON 15, report 11, SQL 7, email 6,
  markdown 6, log 4, chat 3, YAML 2, table 1.
- Duplicate analysis: 0 exact duplicates, 0 near-duplicate pairs, 0
  cross-split near-duplicate pairs.
- Manifest: config and policy SHA-256 recorded; per-file SHA-256 recorded.

The evaluator was also run across seeds 1, 2, 3, 7, 42, 2026, 20260314 and
99999 at 140 cases each; all runs passed every gate (entity-type coverage
31–32, negative ratio 0.136–0.221, multi-domain share 0.250–0.386).

## Reproducibility

Two independent `DatasetGenerator` runs with the same config and seed produced
byte-identical JSON. The artifacts contain no timestamps. `manifest.json`
records the seed and config/policy hashes so a published dataset can be traced
to its inputs.

## Security review

- No runtime dependencies, network calls or telemetry.
- Synthetic-only data: reserved example domains, RFC 1918/5737 and ULA
  networks, documented test card BINs, explicit `FAKE`/`EXAMPLE` credential
  markers, non-parseable PEM labels.
- `tests/test_security.py` scans the generated sample for live-credential
  markers and validates card BINs/Luhn, national-ID checksums, email domains,
  connection strings, IPv4 ranges and PEM labels.
- No real customer data, production endpoint, or proprietary company detail is
  present in the repository or sample dataset.
- Generated data may still trip third-party scanners; label it as synthetic.

## Known limitations

1. Template-family isolation keeps validation/test prompts out of training,
   but a small dataset therefore has fewer distinct families per split. Add
   templates when split diversity matters.
2. Distribution weights are preferences rather than exact quotas. Length and
   difficulty are coupled to template metadata; on the committed sample the
   maximum absolute configured-vs-measured delta is `0.2514` (difficulty 1 is
   over-represented). The evaluator reports all deltas under
   `distribution_fidelity`; gates enforce coverage, not every weight.
2. Negative lookalikes may still be flagged by pattern-only detectors; that is
   the intended false-positive probe, not a label error.
3. Thai names, addresses and organisations are synthetic combinations that
   could coincidentally match real entities.
4. Only documented test card BINs are used. **No PCI DSS compliance is claimed
   or implied.**
5. The default policy file is an illustrative test configuration, not legal
   advice.
6. LLM-generated prompts are not produced by this tool; imported annotations
   require the `verify` stage and human semantic review.
7. No performance, latency or production-readiness claim is made about a
   downstream gateway.
8. The skill description optimization loop and full human evaluation-viewer
   review were not run in this environment (no `claude` CLI / reviewer); the
   skill-behavior prompts are recorded in `evals/evals.json` for the next round.

## Remaining work before a broader public release

- Run the skill behavior evaluations with a human reviewer and, if desired, the
  description optimization loop in an environment with the `claude` CLI.
- Add more medium multi-domain templates so validation/test are less
  family-constrained at small sample sizes.
- Validate against at least one real gateway/detector and publish the measured
  detection/false-positive numbers separately; ground truth alone is not a
  detector benchmark.
- Publish the package to PyPI and run the release checklist on a clean
  machine.
- Consider a signed dataset manifest if datasets will be distributed publicly.

## v2 file-aware evaluation (2026-11-20)

- Dataset: `datasets/v2-sample` (72 cases, 70 attachment files, seed 7,
  profile `real-world-enterprise`, schema `2.0`).
- Commands:
  ```bash
  PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 \
    --config configs/v2/default.json --profile real-world-enterprise \
    --out datasets/v2-sample
  PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 \
    --dataset datasets/v2-sample --json
  PYTHONPATH=src python -m privacy_gateway_testgen verify-v2 \
    --dataset datasets/v2-sample
  PYTHONPATH=src python -m privacy_gateway_testgen report-v2 \
    --dataset datasets/v2-sample --out reports/v2 --check-reproducible
  ```
- Raw results: `reports/v2/evaluation.json`, `reports/v2/evaluation.md`,
  `reports/v2/verification.json`.
- Automated tests: 112 pass (73 v1 + 39 v2), standard library only.

Measured v2 gates:

| Gate | Result | Value | Requirement |
|---|---|---|---|
| schema_validity | PASS | 1.0 | >= 1.0 |
| prompt_span_accuracy | PASS | 1.0 | >= 1.0 |
| file_open_rate | PASS | 1.0 | >= 1.0 |
| extraction_accuracy | PASS | 1.0 | >= 1.0 |
| entity_location_accuracy | PASS | 1.0 | >= 1.0 |
| exact_duplicate_rate | PASS | 0.0 | <= 0.0 |
| near_duplicate_rate | PASS | 0.0 | <= 0.05 |
| document_duplicate_rate | PASS | 0.0 | <= 0.05 |
| file_type_coverage | PASS | csv, docx, jpeg, jpg, json, md, pdf, pptx, txt, xlsx (10) | >= 8 |
| archetype_coverage | PASS | 29 | >= 8 |
| persona_coverage | PASS | 16 | >= 6 |
| intent_coverage | PASS | 20 | >= 8 |
| language_coverage | PASS | th, en, mixed | >= 2 |
| domain_coverage | PASS | pii, payment, secrets, infrastructure | >= 3 |
| negative_share | PASS | 0.25 | >= 0.08 |
| multi_domain_share | PASS | 0.1806 | >= 0.08 |
| attachment_share | PASS | 0.7222 | >= 0.35 |
| ocr_case_coverage | PASS | 5 | >= 1 |
| opening_repetition | PASS | 0.0278 | <= 0.35 |
| repeated_phrase_rate | PASS | 0.0972 | <= 0.20 |
| archetype_concentration | PASS | 0.1111 | <= 0.30 |
| synthetic_safety | PASS | 0 issues | 0 |
| attachment_verification | PASS | 1.0 | == 1.0 |

Counts: 54 positive / 18 negative, 10 ambiguous, 10 multi-domain, 67 fully
verified and 5 `verified_partial` (image/scanned-PDF layout verification).
File counts in the sample: docx 18, xlsx 10, txt 10, pdf 10, csv 7, json 5,
pptx 4, jpg 3, md 2, jpeg 1. Entity density averages 5.375 entities per case.

These numbers are measured from the committed sample. They do not claim OCR
accuracy, a downstream detector's accuracy, or production readiness. The
limitations in `docs/v2-design.md` still apply.

## Conclusion

For **v0.2.0**, the repository's automated tests and all configured quality
gates pass, the v2 file round-trip and security scans are clean, and the v2
sample report contains only measured values. The tool is ready for public
testing as a synthetic dataset generator. It does not certify a gateway, a
legal policy, or PCI DSS compliance, and it should not be presented as having
done so. Image/scanned-PDF OCR accuracy is explicitly not claimed.
