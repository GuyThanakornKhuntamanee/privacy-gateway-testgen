# Security Policy

## Scope

`privacy-gateway-testgen` generates **synthetic** privacy, payment, credential
and infrastructure test data. It is a test-data generator, not a privacy
gateway, DLP engine, or compliance certification tool.

## Safety properties

- No network requests, telemetry, analytics, or third-party dependencies.
- No real customer, patient, employee, or payment data is bundled.
- Emails use reserved domains: `example.com`, `example.org`, `example.net`,
  and `.invalid`.
- Internal names use reserved `.internal` / `.example` names.
- IPv4 values use RFC 1918 private space or RFC 5737 documentation ranges;
  IPv6 uses `fd00::/8` (ULA).
- Cards use documented test BINs (Visa `411111`/`424242`, Mastercard `555555`,
  Discover `601111`, Amex `378282`) and are Luhn-valid. CVVs and expiries are
  synthetic.
- AWS-like access keys contain `FAKE`/`EXAMPLE`.
- PEM blocks use labels such as `EXAMPLE FAKE PRIVATE KEY`, which real TLS/SSH
  parsers reject.
- JWTs have a fixed fake payload and the literal signature
  `example-fake-signature`.
- Cloud resource IDs use account `000000000000` and example resource names.
- `tests/test_security.py` scans a generated dataset for live-credential
  markers and validates these properties.

These controls make values safe to publish. They do **not** prove that a third
party will never misclassify a test value, and they do **not** constitute PCI
DSS, HIPAA, GDPR, PDPA, or any other compliance certification.

## Generated datasets

Generated datasets are synthetic but may still be flagged by DLP scanners,
secret scanners, or antivirus heuristics. Handle them like test fixtures:

1. Label the dataset as synthetic in filenames and repository metadata.
2. Keep real policy files and real detector configurations out of public
   artifacts when they are confidential.
3. Do not merge generated datasets with real customer data.
4. Review the `manifest.json` config/policy hashes before publishing a dataset
   so the provenance is clear.

## Reporting a vulnerability

If you find a real credential, personal record, production endpoint, or
proprietary company detail in the repository or generated output, do not open a
public issue with the value. Report it privately to the maintainers of the
repository where you obtained this project, including:

- the file and line,
- the entity type and why it appears real,
- the generator seed and template if applicable.

Remove or rotate any exposed secret immediately; assume any credential that
looks real may be real.

## Misuse considerations

The tool intentionally produces realistic-looking fake identifiers to test
detection systems. Do not use it to impersonate people, bypass authentication,
or fabricate evidence. The values are non-functional by construction; if a
generated value ever works against a real system, treat that as a severe bug
and report it.

## Dependency and supply-chain posture

- Runtime dependencies: none (Python standard library only).
- Tests: Python standard library `unittest`.
- No package installs are performed by the generator.
- The CI workflow uses GitHub-hosted runners and `actions/setup-python`; pinning
  action SHAs is recommended for hardened deployments.

## Supported versions

Security fixes are applied to the latest `0.x` release until a stable `1.0`
line exists.
