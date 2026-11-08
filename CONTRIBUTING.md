# Contributing

## Setup

Python 3.9+ is required. No third-party packages are needed.

```bash
git clone <repository>
cd privacy-gateway-testgen
PYTHONPATH=src python -m unittest discover -s tests -t . -v
```

Optional editable install:

```bash
python -m pip install -e .
```

## Ground rules

1. **Synthetic data only.** Never add real personal data, live credentials,
   production endpoints, or proprietary company information. Use reserved
   example domains, documentation networks and `example`/`fake` markers.
2. **Span-first.** Do not annotate a finished prompt by regex unless the value
   is unique and the case is verified. Add or extend a template that records
   the span during construction.
3. **Declare the truth.** A template's `domains`, `length_class`, `difficulty`,
   `negative`, `contextual` and `adversarial` metadata must match what it
   actually produces. The test suite checks domains and length classes.
4. **Configurable over hardcoded.** Entity weights, prompt distributions,
   policy actions, and gate thresholds belong in JSON configuration. Avoid
   company-specific or jurisdiction-specific defaults.

## Adding an entity factory

1. Add a function to `src/privacy_gateway_testgen/entities/{pii,payment,secrets,infra,lookalike}.py`
   that returns an `Entity`.
2. Register it as `entity_type: (weight, function)` in that module's
   `GENERATORS`.
3. Ensure the value is non-functional if it resembles a credential, and add a
   check to `tests/test_security.py` if the shape could be mistaken for a live
   secret.
4. Run the tests.

Lookalike factories must set `detection_expected=False` and usually
`valid=False`; use the `note` field to explain the ambiguity.

## Adding a prompt template

1. Add a builder function in `templates.py` using `PromptBuilder.text`,
   `.line`, and `.entity`. Never concatenate `entity.value` directly into the
   prompt — that loses the span.
2. Add a `Template(...)` entry with the real domains, length class, difficulty,
   structure, complexity, detection mode, flags, rationale and tags.
3. For long prompts, call `_pad(b, rng, language, target)` *before* the final
   request so the prompt ends with a task.
4. Run `tests/test_templates.py`; it builds every template in Thai, English and
   mixed language and checks spans, declared domains and length classes.

## Changing policy

Edit `configs/policy.default.json` (or add a new policy file). Keep the action
order complete, scope every rule to domains or entity types, and document any
non-obvious precedence. Then run `validate` over a generated dataset: policy
expectations are recomputed and compared field by field.

The default policy is illustrative. Do not present it as a legal requirement.

## Before opening a pull request

- [ ] `PYTHONPATH=src python -m unittest discover -s tests -t . -v` passes.
- [ ] `python -m privacy_gateway_testgen evaluate --config configs/default.json --out reports --dataset-out datasets/sample` passes.
- [ ] New entity values are synthetic and non-functional.
- [ ] New templates declare accurate metadata and use the builder.
- [ ] Documentation/config examples are updated.
- [ ] No real data or secrets are present in diffs.
- [ ] `README.md` evaluation numbers are updated if the sample changed.

## Style

- Python standard library only.
- Keep functions small and explicit; prefer dataclasses over ad-hoc dicts for
  internal data.
- Comments should explain *why* a non-obvious decision exists, not restate the
  code.
- Error messages should tell the operator what to change.

## License

By contributing, you agree that your contributions are licensed under the MIT
License.
