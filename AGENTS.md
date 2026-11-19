# AGENTS.md

Deterministic synthetic test prompts with exact ground-truth spans for
privacy-aware gateways. The skill (`SKILL.md`) and the Python package
(`src/privacy_gateway_testgen/`) ship together and must stay in agreement.

## Gate

```bash
PYTHONPATH=src python -m unittest discover -s tests -t . -v
PYTHONPATH=src python -m privacy_gateway_testgen evaluate --config configs/default.json --out reports --dataset-out datasets/sample
```

73 tests, ~4 s, standard library only. A change is done when both pass and the
`datasets/sample` + `reports/` diff is intended.

## Invariants

- **Span-first.** Prompts record spans while being built through `PromptBuilder`.
  Annotating a finished prompt with regex loses them.
- **Synthetic only.** Reserved example domains, `example`/`fake` markers, and
  nothing that could behave as a live credential.
- **Declared metadata is truth.** A template's domains, length class,
  difficulty and flags must match what its builder emits.
- **Config over code.** Weights, distributions, policy actions and thresholds
  live in `configs/*.json`.
- **Standard library only.** No new dependencies.
- **Byte-identical output.** The same config and seed reproduce `datasets/` and
  `reports/` exactly; regenerate them when a change alters output.

## Where to look

- Entity factories, template rules, policy precedence, PR checklist → `CONTRIBUTING.md`
- CLI, dataset schema, config keys, quality numbers → `README.md`
- Skill behaviour evals → `evals/README.md`
- Module relationships → graphify (below), not a hand-written map

## Architecture questions

`graphify-out/graph.json` indexes `src/`, `tests/` and `docs/`. Refresh it when
`git rev-parse --short HEAD` differs from `Built from commit` in
`graphify-out/GRAPH_REPORT.md`:

```bash
graphify update .            # ~3 s, no API cost
graphify god-nodes           # architectural hubs
graphify explain "<symbol>"  # what a symbol connects to
graphify affected "<symbol>" # what breaks if it changes
graphify query "<question>"  # orientation across files
```

For exact call sites use Serena's `lsp.find_referencing_symbols`; the graph is
for structure and relationships.
