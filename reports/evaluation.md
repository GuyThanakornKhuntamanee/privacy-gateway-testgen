# Evaluation Report

- Dataset version: `0.1.0`
- Seed: `7`
- Cases: `140`
- Overall: **PASS**

## Quality gates

| Gate | Result | Value | Requirement |
|---|---|---|---|
| schema_validity | PASS | 1.0 | >= 1.0 |
| span_accuracy | PASS | 1.0 | >= 1.0 |
| exact_duplicate_rate | PASS | 0.0 | <= 0.0 |
| near_duplicate_rate | PASS | 0.0 | <= 0.05 |
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
| negative_ratio | PASS | 0.2143 | 0.2 +/- 0.12 |
| multi_domain_share | PASS | 0.2857 | >= 0.12 |
| action_coverage | PASS | ['ALLOW', 'BLOCK', 'LOCAL_ONLY', 'MASK', 'REDACT', 'TOKENIZE'] | all actions; missing=[] |
| split_integrity | PASS | {'family_overlap': [], 'prompt_overlap': []} | no template family or exact prompt crosses splits |
| reproducibility | PASS | True | two runs with the same seed are byte-identical |

## Coverage

- Domains: `{'infrastructure': 0.2071, 'payment': 0.2786, 'pii': 0.45, 'secrets': 0.2214}`
- Languages: `{'en': 0.2643, 'mixed': 0.2571, 'th': 0.4786}`
- Lengths: `{'long': 0.2357, 'medium': 0.3929, 'short': 0.3714}`
- Difficulties: `{'1': 0.3714, '2': 0.1143, '3': 0.2357, '4': 0.2214, '5': 0.0571}`
- Actions: `{'ALLOW': 30, 'BLOCK': 31, 'LOCAL_ONLY': 29, 'MASK': 13, 'REDACT': 33, 'TOKENIZE': 4}`
- Entity types: `31`
- Negative ratio: `0.2143` (target `0.2`)
- Multi-domain share: `0.2857`
- Split counts: `{'train': 112, 'validation': 14, 'test': 14}`

## Duplicate analysis

- Exact duplicate rate: `0.0`
- Near duplicate rate (threshold 0.98): `0.0`
- Near duplicate pairs: `0`

## Configured vs measured distributions

- language delta: `{'en': 0.0143, 'mixed': -0.0429, 'th': 0.0286}`
- length delta: `{'long': -0.0643, 'medium': -0.0071, 'short': 0.0714}`
- difficulty delta: `{'1': 0.2514, '2': -0.0857, '3': -0.0143, '4': -0.0286, '5': -0.1229}`
- domain delta: `{'infrastructure': 0.0071, 'payment': 0.0286, 'pii': 0.15, 'secrets': -0.0286}`
- Maximum absolute delta: `0.2514`

## Known limitations

- Template-family isolation keeps validation/test prompts out of training, but a small dataset therefore has fewer template families per split.
- Negative lookalikes may still be flagged by pattern-only detectors; that is the intended false-positive probe, not a label error.
- Thai names, addresses and organisations are synthetic combinations that could coincidentally match real entities.
- Only documented test card BINs are used. No PCI DSS compliance is claimed or implied.
- The default policy file is an illustrative test configuration, not legal advice.
- LLM-generated prompts are not produced by this tool; imported annotations must be checked with the separate verification command before they are trusted.
- No performance, latency or production-readiness claim is made by the evaluator.
- Language, length, difficulty and domain weights are preferences, not exact quotas: prompt length and difficulty are coupled to the available template families, so the configured distribution can drift. The evaluator reports configured-vs-measured deltas.

## Recommended improvements

- Add organisation-specific entity factories and policy files before deployment.
- Grow the template inventory when validation/test diversity matters more than dataset size.
- Run the manual review workflow for any LLM-authored cases before using them as ground truth.
- Re-run this evaluator after every template, factory or policy change.
