# Release Checklist

Run every item before publishing a tag. Do not publish if any gate fails.

## 1. Freeze scope

- [ ] Version bumped in `pyproject.toml` and
      `src/privacy_gateway_testgen/__init__.py`.
- [ ] `CHANGELOG.md` updated (or release notes drafted) with user-visible
      changes, schema changes, and policy-default changes.
- [ ] `dataset_version` in `configs/default.json` bumped if the generated data
      changes.

## 2. Verify the code

- [ ] `PYTHONPATH=src python -m unittest discover -s tests -t . -v` — all pass.
- [ ] No skipped tests for functionality that is claimed to work.
- [ ] No third-party runtime imports.
- [ ] `python -m compileall src` succeeds.

## 3. Verify the data

- [ ] Regenerate the sample: `generate --config configs/default.json --out datasets/sample`.
- [ ] `validate` passes on `all.jsonl`, `train.jsonl`, `validation.jsonl`,
      `test.jsonl`.
- [ ] `evaluate` passes with the shipped config and writes
      `reports/evaluation.json` / `.md`.
- [ ] Split integrity is clean (no template family or near-duplicate across
      splits).
- [ ] All six actions appear in the sample.
- [ ] Security scan tests pass; inspect any new entity shape manually.
- [ ] Manifest hashes match the committed files.

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
