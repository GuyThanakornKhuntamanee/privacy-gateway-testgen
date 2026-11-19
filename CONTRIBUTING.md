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
5. **A file is not verified when it renders.** For v2, reopen it with a parser,
   resolve every recorded location, and mark image/scanned-PDF cases
   `verified_partial` unless an OCR engine actually ran.
6. **One scenario per case.** Shared people, hosts, database endpoints, IDs,
   timestamps and transactions come from `v2/scenario.py`. Do not draw a fresh
   value for a field that another attachment is supposed to reference.
7. **Language is per attachment.** Use `ctx.doc_language` and the localization
   layer; a `mixed` document must contain both Thai and English script. PDF and
   image renderers are Latin-only and raise on Thai text; route instead of
   substituting `?`.
8. **Structure references must resolve.** A prompt may cite a sheet, page,
   section, row, slide or key only when the attachment's `structure` proves it
   exists.

## Adding a v2 document archetype

1. Add a builder in `src/privacy_gateway_testgen/v2/archetypes.py` using
   `DocBuilder`. Insert entities through `.para`, `.table` and `.record`; never
   append `entity.value` directly. Use `ctx.shared(...)` for values another
   attachment must match, and `ctx.date()` / `ctx.money()` for Thai-aware
   formatting.
2. Write static labels in English; `localize_doc` (called by the generator)
   translates headings, headers, prose and notes without touching entity spans.
   Add new labels to `v2/localization.py` when needed.
2. Declare the real category, domains, supported renderers, difficulty and
   rationale in the `ARCHETYPES` registry. Keep the builder's output consistent
   with that declaration.
3. If the document needs a header/footer, hidden sheet, XML root or OCR style,
   set it through `builder.build(...)` or `doc.metadata`, not through a
   post-render search.
4. Run `tests/test_v2_renderers.py` and `tests/test_v2_generation.py`; all
   supported formats must reopen and verify.

## Adding a v2 renderer

1. Implement `render_*` in `v2/renderers/` and return a `RenderedFile` with the
   MIME type, extraction method, and every entity location.
2. Register the extension in `v2/renderers/__init__.py` and add it to
   `SUPPORTED_FORMATS` through its family set.
3. Add the corresponding extraction and verification path to `v2/extract.py`.
   A renderer is not production-ready until the round-trip test passes.
4. Do not add a dependency. OOXML uses `zipfile` + XML, PNG uses `zlib`, JPEG is
   encoded locally, and PDF is written directly.

## v2 prompt realism

Prompt builders live in `v2/realism.py`. Keep the sensitive data incidental:
the prompt should read like a workplace request, not like an instruction to
detect a category. When adding a phrase, keep the Thai/English/mixed variants
and the imperfection path. Do not make every example ungrammatical; typo rate is
configuration.

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
- [ ] `python -m privacy_gateway_testgen validate-v2 --dataset datasets/v2-sample` and `verify-v2 --dataset datasets/v2-sample` pass.
- [ ] `python -m privacy_gateway_testgen report-v2 --dataset datasets/v2-sample --out reports/v2` passes.
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
