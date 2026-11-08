# Skill Behavior Evaluation

This is a compact, real evaluation of the skill in an agent harness. It is not
the full skill-creator viewer loop: no human reviewer or with/without baseline
was available in this build environment. The prompts are recorded in
`evals/evals.json` for a future full round.

## Method

Two independent general-purpose agents were given the skill directory and
asked to read `SKILL.md` and follow it. Outputs were written outside the
repository (temporary directory) so the source and committed sample were not
modified.

### Run 1 — generate and evaluate

Prompt: generate a reproducible 140-case dataset (seed 7) covering all four
domains with negative cases, validate it, and pass the quality gates; report
exact commands, gates, coverage and limitations.

Observed result:

- Used the repository CLI with `PYTHONPATH=src`; did not invent offsets.
- 140 cases, splits 112/14/14, 0 validation issues.
- All 25 gates passed, evaluator exit 0, `failed_gates: []`.
- Schema/span accuracy 1.0, exact/near duplicates 0.0, reproducibility true.
- Coverage: all four domains, 33 negatives (23.6%), 107 positives, 21
  adversarial, 32 entity types, 559 annotations.
- Actions: ALLOW 33, BLOCK 33, LOCAL_ONLY 29, REDACT 26, MASK 13, TOKENIZE 6.
- Independent second generation produced byte-identical `all.jsonl`; manifest
  hashes matched.
- Reported a real limitation: configured weights are not exact quotas
  (difficulty 1 measured 42.1% vs 12% target).
- Reported that the naive `unittest` invocation needs `-t .`.

### Run 2 — imported annotation verification

Prompt: verify an imported JSONL with suspicious offsets, repair only
unambiguous spans, and avoid treating repaired labels as authoritative truth.

Observed result:

- 2 cases / 2 spans: 1 repaired (unique occurrence), 1 unresolved (value
  appears twice), exit code 1 as expected.
- Correctly explained that span repair is not semantic verification.
- Additionally flagged that the "valid" national ID label in the imported case
  fails the Thai checksum, and that `valid: true` was unaudited.
- Found a real bug: the CLI could not read a UTF-8 BOM JSONL produced by
  Windows PowerShell.

## Changes made from the evaluation

- `cli._load_cases`, `load_config` and `load_policy` now read `utf-8-sig`, so
  BOM-prefixed JSON/JSONL files work on Windows.
- `validate_case` now rejects expected Thai national IDs that fail the checksum
  and expected card numbers that fail Luhn.
- `verify` now emits `validity_warnings` for the same cases, so an offset
  repair cannot silently bless a semantically wrong label.
- `evaluate` now reports `distribution_fidelity` (configured vs measured
  language/length/difficulty/domain deltas) and the docs describe weights as
  preferences rather than exact quotas.
- `SKILL.md` now documents the exact test command, including `-t .`.

The fixes were re-tested after the evaluation; the suite and gates pass.

## Honest limitations

- No baseline (without-skill) runs, so this is a behavior smoke test, not an
  A/B benchmark.
- No human review of the generated outputs beyond the two agent reports.
- The sub-agent runs happened before the BOM/validity/fidelity fixes; the
  findings are the reason those changes exist, not a claim that the earlier
  build was final.
- Timing/token metrics were not captured in a comparable form.
