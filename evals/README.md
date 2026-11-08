# Skill Behavior Evaluations

`evals.json` contains realistic user prompts for evaluating the skill in an
agent harness. They cover generation, negative cases, mixed-domain policy
routing, imported-annotation verification, and a read-only audit.

## Status

Two skill-guided agent runs were completed (generation/evaluation and imported-
annotation verification); results and the bugs they exposed are summarized in
[`../docs/skill-evaluation.md`](../docs/skill-evaluation.md). The full
with-skill / without-skill benchmark and human review loop have **not** been
run. The repository's quantitative evidence is the automated test suite plus
the quality gates in `reports/evaluation.json` /
`docs/evaluation-report.md`.

## Running an evaluation later

For each eval, start a fresh agent session with access to this skill directory
and give it the prompt. Save outputs under
`privacy-gateway-testgen-workspace/iteration-N/eval-<id>/with_skill/outputs/`.
Run the same prompt without the skill for a baseline, then compare:

- Did the agent use the generator/validator/evaluator instead of inventing
  offsets?
- Did it report measured gate results instead of claiming success?
- Did it keep all data synthetic?
- Did it mark imported annotations as unverified until review?
- Did it refuse to present the illustrative policy as legal advice?

The skill-creator `eval-viewer/generate_review.py` can render the runs once
they exist.
