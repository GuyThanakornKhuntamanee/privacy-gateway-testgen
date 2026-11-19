# v2 sample dataset

Synthetic file-aware dataset generated with schema `2.1`, seed `7`, profile
`real-world-enterprise`:

```bash
PYTHONPATH=src python -m privacy_gateway_testgen generate-v2 \
  --config configs/v2/default.json --profile real-world-enterprise \
  --out datasets/v2-sample
```

- 72 cases, 62 attachment files
- 9 file types: CSV, DOCX, JPG, JSON, MD, PDF, PNG, TXT, XLSX
- Prompt languages: Thai 39, English 19, mixed 14
- Attachment languages: Thai 12, English 29, mixed 21; 12 language pairs
- 11 negative and 9 ambiguous cases
- 8 OCR-oriented image/scanned-PDF cases (`verified_partial`)
- 16 structure-reference cases; 6 cross-file-link cases; all consistency checks pass
- 12 multi-file cases, including 2 old/new and 1 same-archetype bundle

`cases.jsonl` is the case list, `ground_truth/entities.jsonl` is the flattened
annotation list, `attachments/<test_id>/` holds the real files, and
`manifest.json` records versions, seed, distributions, hashes and verification
status. All content is synthetic and non-functional. Do not add real customer
data, credentials or production infrastructure.

Thai PDF/image requests are routed to English and recorded in
`language_routing`; they are not silently rendered with `?`. Image/scanned-PDF
cases are layout-verified, not OCR-verified.

Re-verify the dataset from disk:

```bash
PYTHONPATH=src python -m privacy_gateway_testgen validate-v2 --dataset datasets/v2-sample
PYTHONPATH=src python -m privacy_gateway_testgen verify-v2 --dataset datasets/v2-sample
```
