# AGENTS.md

Deterministic synthetic test prompts, real attachment files and exact
ground-truth locations for privacy-aware gateways. The skill (`SKILL.md`) and the
Python package (`src/privacy_gateway_testgen/`) ship together and must stay in
agreement.

## Gate

```bash
PYTHONPATH=src python -m unittest discover -s tests -t . -v
PYTHONPATH=src python -m privacy_gateway_testgen evaluate --config configs/default.json --out reports --dataset-out datasets/sample
PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 --config configs/v2/default.json --profile benchmark-balanced --out datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen verify-v2 --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen report-v2 --dataset datasets/v2-sample --out reports/v2 --check-reproducible
PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 --config configs/v2/default.json --profile thai-rendering --count 16 --out datasets/v2-thai-sample
PYTHONPATH=src python -m privacy_gateway_testgen report-v2 --dataset datasets/v2-thai-sample --out reports/v2-thai --check-reproducible
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 --dataset datasets/compat/v2.0-sample
```

197 tests, ~30 s. A change is done when all pass, `benchmark_ready` is `true`
(or its reasons are intended), and the `datasets/sample`, `datasets/v2-sample`,
`datasets/v2-thai-sample` and `reports/` diffs are intended.

## Invariants

- **Span-first.** Prompts and attachments record entity positions while being
  built. Annotating a finished file with regex loses them.
- **Verified files.** A renderer returning bytes is not success. Every v2
  attachment is reopened with a parser and every location is resolved.
- **Synthetic only.** Reserved example domains, `example`/`fake` markers, and
  nothing that could behave as a live credential.
- **Declared metadata is truth.** A template/archetype's domains, length class,
  difficulty, renderers and flags must match what its builder emits.
- **Config over code.** Weights, distributions, policy actions and thresholds
  live in `configs/*.json`.
- **Dependencies are declared, pinned and justified.** Runtime deps are
  `Pillow` (raster + Thai shaping), `reportlab` (native PDF) and `pypdf` (PDF
  verification); everything else is stdlib. Add one only when it materially
  improves correctness, and document it in `docs/v2.2-thai-rendering-design.md`.
- **Byte-identical output.** The same config and seed reproduce `datasets/` and
  `reports/` exactly; regenerate them when a change alters output. Byte identity
  holds for one pinned dependency set; across Pillow/ReportLab versions only the
  content (text, spans, boxes, case JSON) is claimed identical.
- **OCR is not assumed.** Image/scanned-PDF cases are layout-verified and
  marked `verified_partial` unless an OCR engine actually ran.
- **Per-attachment language.** A case may mix Thai and English attachments;
  `mixed` must contain both scripts in the same file. PDF and raster renderers
  carry Thai, English and mixed; only `log` is English-only. Keep the
  `language_routing` mechanism and fail rather than write `?`.
- **One scenario per case.** Shared people, hosts, IDs, dates and transactions
  come from `v2/scenario.py`; `cross_file_links` and `consistency_checks` are
  validated, not assumed.
- **Structure references resolve.** A prompt may cite a sheet/page/section/row
  only when the referenced attachment structure proves it exists, and only when
  a reader could see it (never row/column on a flat image).
- **Checks have status.** `passed` / `failed` / `not_applicable` /
  `not_evaluated` with `evaluated_items`; empty input is never a pass.
- **Benchmark readiness is measured.** `report-v2 --check-reproducible` computes
  `benchmark_ready` and the safe subset; a smaller honest dataset beats a larger
  inconsistent one.

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
