# Publishing to PyPI

The package is published from `.github/workflows/publish.yml` with
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — no API token is
stored in the repository or on a developer machine.

## What the maintainer does once

1. Create a <https://pypi.org> account and verify the email address.
2. Enable two-factor authentication (PyPI requires it for maintainers).
3. Add a **pending publisher** at <https://pypi.org/manage/account/publishing/>
   with exactly these values:

   | Field | Value |
   |---|---|
   | PyPI project name | `privacy-gateway-testgen` |
   | Owner | `GuyThanakornKhuntamanee` |
   | Repository name | `privacy-gateway-testgen` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

4. Optional rehearsal: repeat step 3 on <https://test.pypi.org> with environment
   name `testpypi` (same workflow name).

Nothing else is required: the first successful upload creates the project, so the
name does not need to be reserved first.

## Release a version

1. Bump the version in `pyproject.toml` and `src/privacy_gateway_testgen/__init__.py`
   (they must match), add a `CHANGELOG.md` entry, regenerate the samples when the
   output changed, run the gate, and commit to `main`.
2. Create the git tag and GitHub release:
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   gh release create vX.Y.Z --verify-tag --title "vX.Y.Z" --notes-file notes.md
   ```
   Publishing the release triggers `publish.yml`, which builds the wheel and
   sdist, runs `twine check`, and uploads them to PyPI through OIDC.
3. Verify:
   ```bash
   python -m pip install --index-url https://pypi.org/simple privacy-gateway-testgen==X.Y.Z
   privacy-gateway-testgen --version
   ```

## Rehearse on TestPyPI

Run the workflow manually with target `testpypi`
(Actions → Publish → Run workflow), then:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple privacy-gateway-testgen
```

TestPyPI does not keep dependencies, hence the extra index.

## Manual upload (fallback)

Only when Trusted Publishing is unavailable. Create a project-scoped API token on
PyPI and keep it out of the repository:

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*          # username: __token__
```

## Rules

- A version number cannot be reused once uploaded; yank it instead of deleting.
- Never upload `datasets/` or `reports/` — they are repository artifacts, not
  package data.
- The wheel is pure Python (`py3-none-any`) but requires `Pillow`, `reportlab`
  and `pypdf` at runtime; dependencies are resolved from PyPI, so an offline
  install needs `pip download` for those as well.
- The bundled Sarabun font (SIL OFL 1.1) ships inside the wheel with its license
  text; do not strip `assets/fonts/OFL.txt`.
