# Release Checklist

Run every item before publishing a tag. Do not publish if any gate fails.

## 1. Freeze scope

- [ ] Version bumped in `pyproject.toml` and
      `src/privacy_gateway_testgen/__init__.py`.
- [ ] `CHANGELOG.md` updated (or release notes drafted) with user-visible
      changes, schema changes, and policy-default changes.
- [ ] `dataset_version` in `configs/default.json` bumped if the generated data
      changes; v2 sample version in `configs/v2/default.json` bumped if v2 data
      changes.
- [ ] `schemas/testcase.v2.schema.json` and `docs/v2-design.md` are current if
      schema 2.1 changed.
- [ ] `docs/capability-matrix.md` matches the renderers and the checked language
      capabilities.

## 2. Verify the code

- [ ] `PYTHONPATH=src python -m unittest discover -s tests -t . -v` — all pass.
- [ ] No skipped tests for functionality that is claimed to work.
- [ ] No third-party runtime imports.
- [ ] `python -m compileall src` succeeds.
- [ ] Each v2 renderer family reopens and verifies (`tests/test_v2_renderers.py`).

## 3. Verify the data

- [ ] Regenerate the sample: `generate --config configs/default.json --out datasets/sample`.
- [ ] Regenerate the v2 sample:
      `generate-v2 --config configs/v2/default.json --profile real-world-enterprise --out datasets/v2-sample`.
- [ ] `validate` passes on `all.jsonl`, `train.jsonl`, `validation.jsonl`,
      `test.jsonl`.
- [ ] `validate-v2 --dataset datasets/v2-sample` and
      `verify-v2 --dataset datasets/v2-sample` pass.
- [ ] `evaluate` passes with the shipped config and writes
      `reports/evaluation.json` / `.md`.
- [ ] `report-v2 --dataset datasets/v2-sample --out reports/v2` passes and
      writes `evaluation.json`, `evaluation.md`, `verification.json`.
- [ ] Split integrity is clean (no template family or near-duplicate across
      splits).
- [ ] Language gate passes: Thai documents contain Thai, mixed documents contain
      both scripts, and PDF/image attachments are English with a routing reason.
- [ ] Prompt/attachment language matrix is reported and non-trivial.
- [ ] `cross_file_links` are consistent and `consistency_checks` all pass.
- [ ] Every `structure_reference` resolves to a real sheet/page/section/row.
- [ ] Old/new and same-archetype bundles show a traceable change.
- [ ] All six actions appear in the sample.
- [ ] Security scan tests pass; inspect any new entity shape manually.
- [ ] Manifest hashes match the committed files, including v2 attachment hashes.
- [ ] No Office macro, PDF JavaScript, external relationship or executable is
      present in generated attachments.
- [ ] Image/scanned-PDF cases are marked `verified_partial`; no OCR accuracy is
      claimed without an OCR run.

## 4. Review the documentation

- [ ] `README.md` commands work from a clean checkout.
- [ ] Evaluation numbers in the README match the latest report.
- [ ] `SECURITY.md` reflects any new data shape.
- [ ] `docs/architecture.md` and `docs/acceptance-criteria.md` are current.
- [ ] `SKILL.md` frontmatter name/description match the skill directory.

## 5. Security review

- [ ] No real personal data, production endpoints, live credentials or
      proprietary company details in the repository or sample dataset.
- [ ] Cards use documented test BINs only.
- [ ] PEM/JWT/AWS-like values remain explicitly fake.
- [ ] Emails use reserved example domains; IPs use RFC 1918/5737 or ULA.
- [ ] No secrets, API keys or tokens in CI config or documentation.

## 6. Package and publish

- [ ] `python -m build` produces sdist and wheel (requires the `build` package
      only in the release environment; it is not a runtime dependency).
- [ ] Install the wheel in a fresh virtual environment and run `generate`,
      `validate`, and `evaluate`.
- [ ] Tag the release (`vX.Y.Z`) and attach the wheel, sdist, sample dataset,
      evaluation report, and SBOM if applicable.
- [ ] Announce the release with the measured gate results and known
      limitations — not only the feature list.

## 7. Post-release

- [ ] Verify the published package installs and the CLI entry point works.
- [ ] Archive the evaluation report for the released commit.
- [ ] Open issues for deferred limitations rather than silently accepting
      them.
